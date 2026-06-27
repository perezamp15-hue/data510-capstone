import os
import re
import requests
import pandas as pd
from pybaseball import statcast_by_date
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime

def get_db_connection():
    """Connects via Railway URL environment string or fallback local config."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)
    return psycopg2.connect(
        dbname="baseball_models", user="postgres", password="your_password", host="localhost", port=5432
    )

def fetch_mlb_api_game_details(game_id):
    """
    Queries the official MLB StatsAPI to pull dimensions missing from Statcast:
    Lineups, precise umpire entries, and raw weather arrays.
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_id}/feed/live"
    try:
        res = requests.get(url, timeout=10).json()
        live_data = res.get("liveData", {})
        boxscore = live_data.get("boxscore", {})
        game_data = res.get("gameData", {})
        
        # 1. Lineup Arrays
        home_lineup = [
            int(boxscore["teams"]["home"]["players"][p]["person"]["id"]) 
            for p in boxscore.get("teams", {}).get("home", {}).get("battingOrder", [])
        ]
        away_lineup = [
            int(boxscore["teams"]["away"]["players"][p]["person"]["id"]) 
            for p in boxscore.get("teams", {}).get("away", {}).get("battingOrder", [])
        ]
        
        # 2. Extract Home Plate Umpire
        home_plate_umpire_name = None
        for official in live_data.get("officials", []):
            if official.get("officialType") == "Home Plate":
                home_plate_umpire_name = official["official"]["fullName"]
                
        # 3. Environment Specs from Boxscore Data
        weather_str = ""
        for item in boxscore.get("info", []):
            if item.get("label") == "Weather":
                weather_str = item.get("value", "")
                
        # Regex parse: "72 degrees, clear, wind 5 mph out to CF"
        temp = int(re.search(r'(\d+)\s*degrees', weather_str).group(1)) if re.search(r'(\d+)\s*degrees', weather_str) else None
        wind_speed = float(re.search(r'wind\s*(\d+)\s*mph', weather_str).group(1)) if re.search(r'wind\s*(\d+)\s*mph', weather_str) else None
        
        wind_dir = None
        if "out to" in weather_str:
            wind_dir = "Out to " + weather_str.split("out to")[-1].strip()
        elif "in from" in weather_str:
            wind_dir = "In from " + weather_str.split("in from")[-1].strip()

        return {
            "home_lineup": home_lineup if home_lineup else None,
            "away_lineup": away_lineup if away_lineup else None,
            "umpire_name": home_plate_umpire_name,
            "temp": temp,
            "wind_speed": wind_speed,
            "wind_direction": wind_dir
        }
    except Exception as e:
        print(f"[-] Warning: Failed to fetch MLB StatsAPI context for game {game_id}: {e}")
        return None

def ingest_master_pipeline(target_date: str):
    """Orchestrates ingestion across all relational dependencies."""
    print(f"[***] Starting Production ETL Pipeline for Date: {target_date} [***]")
    
    # Fetch base Statcast tracking records
    df = statcast_by_date(target_date)
    if df.empty:
        print("[-] Stopped: No historical pitches returned for this date.")
        return
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Step 1: Handle Players (Dim)
        print("[*] Processing Player Dimension Layer...")
        pitchers = df[['pitcher', 'player_name']].drop_duplicates().rename(columns={'pitcher': 'id'})
        batters = df[['batter', 'player_name']].drop_duplicates().rename(columns={'batter': 'id'})
        players_combined = pd.concat([pitchers, batters]).drop_duplicates(subset=['id'])
        
        player_tuples = [(int(row['id']), row['player_name']) for _, row in players_combined.iterrows()]
        execute_values(cursor, """
            INSERT INTO dim_players (player_id, player_name) VALUES %s
            ON CONFLICT (player_id) DO NOTHING;
        """, player_tuples)
        
        # Step 2: Loop unique match logs to populate Umpires and Games
        unique_game_ids = df['game_pk'].dropna().unique().astype(int)
        print(f"[*] Processing API overlaps for {len(unique_game_ids)} unique games...")
        
        for g_id in unique_game_ids:
            api_data = fetch_mlb_api_game_details(g_id)
            game_slice = df[df['game_pk'] == g_id].iloc[0]
            
            umpire_id = None
            if api_data and api_data["umpire_name"]:
                # Upsert umpire dynamically to maintain relational integrity
                cursor.execute("""
                    INSERT INTO fact_umpire_biases (umpire_name) 
                    VALUES (%s) ON CONFLICT (umpire_name) DO UPDATE SET historical_games_called = fact_umpire_biases.historical_games_called + 1
                    RETURNING umpire_id;
                """, (api_data["umpire_name"],))
                umpire_id = cursor.fetchone()[0]

            # Upsert detailed Game context record
            cursor.execute("""
                INSERT INTO dim_games (
                    game_id, game_date, home_team, away_team, umpire_id,
                    home_lineup, away_lineup, game_temperature, game_wind_speed, game_wind_direction
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id) DO NOTHING;
            """, (
                int(g_id), target_date, game_slice['home_team'], game_slice['away_team'], umpire_id,
                api_data["home_lineup"] if api_data else None,
                api_data["away_lineup"] if api_data else None,
                api_data["temp"] if api_data else None,
                api_data["wind_speed"] if api_data else None,
                api_data["wind_direction"] if api_data else None
            ))

        # Step 3: Stream Pitch records into Partitioned Fact Table
        print("[*] Processing Pitch Fact logs...")
        df_cleaned = df.dropna(subset=['game_pk', 'pitcher', 'batter', 'inning'])
        pitch_tuples = []
        
        for _, r in df_cleaned.iterrows():
            pitch_tuples.append((
                int(r['game_pk']), int(r['pitcher']), int(r['batter']), int(r['inning']), r['inning_topbot'],
                int(r['balls']), int(r['strikes']), int(r['outs']), r['pitch_type'], 
                float(r['release_speed']) if pd.notna(r['release_speed']) else None,
                int(r['release_spin_rate']) if pd.notna(r['release_spin_rate']) else None,
                float(r['plate_x']) if pd.notna(r['plate_x']) else None,
                float(r['plate_z']) if pd.notna(r['plate_z']) else None,
                float(r['launch_speed']) if pd.notna(r['launch_speed']) else None,
                int(r['launch_angle']) if pd.notna(r['launch_angle']) else None,
                r['events'] if pd.notna(r['events']) else 'pitch'
            ))
            
        execute_values(cursor, """
            INSERT INTO fact_pitches (
                game_id, pitcher_id, batter_id, inning, inning_topbot, 
                balls, strikes, outs, pitch_type, velocity, spin_rate,
                plate_x, plate_z, exit_velocity, launch_angle, play_result
            ) VALUES %s;
        """, pitch_tuples)
        
        # Step 4: Recompute Intermediate Rolling Aggregates for the Next Slate
        print("[*] Running Post-Game Analytical Calculations...")
        cursor.execute("""
            INSERT INTO fact_daily_player_stats (stat_date, player_id, hitter_rolling_15_ops, hitter_whiff_rate)
            SELECT 
                %s::DATE as stat_date,
                f.batter_id as player_id,
                (COUNT(CASE WHEN f.play_result IN ('single','double','triple','home_run','walk') THEN 1 END)::NUMERIC / NULLIF(COUNT(f.pitch_id), 0)) as hitter_rolling_15_ops,
                (COUNT(CASE WHEN f.is_swing = TRUE AND f.is_contact = FALSE THEN 1 END)::NUMERIC / NULLIF(COUNT(CASE WHEN f.is_swing = TRUE THEN 1 END), 0)) * 100 as hitter_whiff_rate
            FROM fact_pitches f
            JOIN dim_games g ON f.game_id = g.game_id
            WHERE g.game_date BETWEEN %s::DATE - INTERVAL '16 days' AND %s::DATE
            GROUP BY f.batter_id
            ON CONFLICT (stat_date, player_id) DO UPDATE SET
                hitter_rolling_15_ops = EXCLUDED.hitter_rolling_15_ops,
                hitter_whiff_rate = EXCLUDED.hitter_whiff_rate;
        """, (target_date, target_date, target_date))
        
        conn.commit()
        print(f"[***] DATABASE SYNC COMPLETE FOR TARGET SLATE: {target_date} [***]")
        
    except Exception as e:
        conn.rollback()
        print(f"[!] Critical Processing Rollback: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Test slate
    run_date = (datetime.utcnow() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    ingest_master_pipeline(run_date)
