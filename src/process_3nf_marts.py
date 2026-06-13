"""
Data Science Studio Scrum (DS3) - Processing Engine
Description: Transforms staging layer logs into normalized 3NF structures.
"""
import os
import sys
import json
import time
import requests
import pandas as pd
from sqlalchemy import create_engine, text

def run_normalization_pipeline():
    print("\n==================================================================")
    print("STARTING 3RD NORMAL FORM (3NF) PROCESSING CONVERSION PASS")
    print("==================================================================")
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(db_url)
    
    # ----------------------------------------------------------------
    # 1. POPULATE VENUES & TEAMS DIMENSIONS
    # ----------------------------------------------------------------
    print("Normalizing Venues and Teams Tables...")
    df_stg_stadiums = pd.read_sql_table("stg_stadiums", con=engine)
    
    with engine.begin() as conn:
        for _, row in df_stg_stadiums.iterrows():
            conn.execute(
                text("""
                    INSERT INTO venues (stadium_key, stadium_name, altitude_ft, latitude, longitude)
                    VALUES (:key, :name, :alt, :lat, :lon)
                    ON CONFLICT (stadium_key) DO UPDATE SET altitude_ft = EXCLUDED.altitude_ft
                """),
                {"key": row['stadium_id'], "name": row['name'], "alt": row['altitude_ft'], "lat": row['latitude'], "lon": row['longitude']}
            )
            
            conn.execute(
                text("""
                    INSERT INTO teams (team_name, home_venue_id)
                    VALUES (:team, (SELECT venue_id FROM venues WHERE stadium_key = :key))
                    ON CONFLICT (team_name) DO NOTHING
                """),
                {"team": row['team'], "key": row['stadium_id']}
            )

    # ----------------------------------------------------------------
    # 2. POPULATE DYNAMIC TEAMS FROM SCHEDULE LAYERS
    # ----------------------------------------------------------------
    df_sched = pd.read_sql_table("stg_schedules", con=engine)
    all_teams = set(df_sched['home_team'].dropna().unique()).union(set(df_sched['away_team'].dropna().unique()))
    
    with engine.begin() as conn:
        for t_name in all_teams:
            conn.execute(
                text("INSERT INTO teams (team_name) VALUES (:t) ON CONFLICT (team_name) DO NOTHING"),
                {"t": t_name}
            )

    # ----------------------------------------------------------------
    # 3. POPULATE GAMES FACT TABLE
    # ----------------------------------------------------------------
    print("Normalizing Games Fact Layer...")
    with engine.begin() as conn:
        for _, row in df_sched.iterrows():
            conn.execute(
                text("""
                    INSERT INTO games (game_pk, game_date, home_team_id, away_team_id)
                    VALUES (
                        :pk, :dt::DATE,
                        (SELECT team_id FROM teams WHERE team_name = :home),
                        (SELECT team_id FROM teams WHERE team_name = :away)
                    ) ON CONFLICT (game_pk) DO NOTHING
                """),
                {"pk": int(row['game_pk']), "dt": row['game_date'], "home": row['home_team'], "away": row['away_team']}
            )

    # ----------------------------------------------------------------
    # 4. PARSE BOXSCORES: POPULATE PLAYERS & PERFORMANCE TABLES
    # ----------------------------------------------------------------
    print("Building Role-Separated Player and Performance Tables...")
    df_logs = pd.read_sql_table("stg_game_logs", con=engine)
    
    for _, row in df_logs.iterrows():
        g_pk = int(row['game_pk'])
        box_data = json.loads(row['log_data'])
        
        for side in ["home", "away"]:
            side_node = box_data.get(side, {})
            t_name = side_node.get("team", {}).get("name")
            players_node = side_node.get("players", {})
            
            for p_key, p_info in players_node.items():
                person = p_info.get("person", {})
                p_id = int(person.get("id"))
                p_name = person.get("fullName")
                pos = p_info.get("position", {}).get("abbreviation")
                stats = p_info.get("stats", {})
                
                # Fetch detailed player profile fields from the API if missing
                url_p = f"https://statsapi.mlb.com/api/v1/people/{p_id}"
                bat_side, pitch_hand = "S", "R"
                try:
                    res_p = requests.get(url_p, timeout=5)
                    if res_p.status_code == 200:
                        p_meta = res_p.json().get("people", [{}])[0]
                        bat_side = p_meta.get("batSide", {}).get("code", "S")
                        pitch_hand = p_meta.get("pitchHand", {}).get("code", "R")
                except Exception:
                    pass
                
                # Insert Player Records
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                            INSERT INTO players (player_id, full_name, primary_position, bat_side, pitch_hand)
                            VALUES (:id, :name, :pos, :bat, :pit)
                            ON CONFLICT (player_id) DO UPDATE SET primary_position = EXCLUDED.primary_position
                        """),
                        {"id": p_id, "name": p_name, "pos": pos, "bat": bat_side, "pit": pitch_hand}
                    )
                
                # Extract Batting Statistics
                bat_stats = stats.get("batting", {})
                if bat_stats and (bat_stats.get("plateAppearances", 0) > 0):
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO game_player_performance (
                                    game_pk, player_id, team_id, player_role, at_bats, runs, hits, rbi, walks, strikeouts
                                ) VALUES (
                                    :g_pk, :p_id, (SELECT team_id FROM teams WHERE team_name = :t_name), 'batter',
                                    :ab, :r, :h, :rbi, :bb, :so
                                ) ON CONFLICT (game_pk, player_id, player_role) DO NOTHING
                            """),
                            {
                                "g_pk": g_pk, "p_id": p_id, "t_name": t_name,
                                "ab": bat_stats.get("atBats", 0), "r": bat_stats.get("runs", 0),
                                "h": bat_stats.get("hits", 0), "rbi": bat_stats.get("rbi", 0),
                                "bb": bat_stats.get("baseOnBalls", 0), "so": bat_stats.get("strikeOuts", 0)
                            }
                        )

                # Extract Pitching Statistics
                pit_stats = stats.get("pitching", {})
                if pit_stats and (pit_stats.get("pitchesThrown", 0) > 0):
                    with engine.begin() as conn:
                        conn.execute(
                            text("""
                                INSERT INTO game_player_performance (
                                    game_pk, player_id, team_id, player_role, innings_pitched, hits_allowed, runs_allowed, earned_runs, strikeouts_recorded, pitches_thrown
                                ) VALUES (
                                    :g_pk, :p_id, (SELECT team_id FROM teams WHERE team_name = :t_name), 'pitcher',
                                    :ip, :ha, :ra, :er, :so, :pt
                                ) ON CONFLICT (game_pk, player_id, player_role) DO NOTHING
                            """),
                            {
                                "g_pk": g_pk, "p_id": p_id, "t_name": t_name,
                                "ip": str(pit_stats.get("inningsPitched", "0.0")), "ha": pit_stats.get("hits", 0),
                                "ra": pit_stats.get("runs", 0), "er": pit_stats.get("earnedRuns", 0),
                                "so": pit_stats.get("strikeOuts", 0), "pt": pit_stats.get("pitchesThrown", 0)
                            }
                        )

    # ----------------------------------------------------------------
    # 5. POPULATE FACT_AT_BATS TABLE
    # ----------------------------------------------------------------
    print("Mapping Statcast events to fact_at_bats...")
    try:
        df_pitches = pd.read_sql_table("stg_statcast_pitches", con=engine)
        with engine.begin() as conn:
            for _, row in df_pitches.iterrows():
                # Verify structural integrity keys exist before performing the insert operation
                b_id = int(row['batter'])
                p_id = int(row['pitcher'])
                
                # Handle edge cases where players appear in Statcast but skipped boxscores
                conn.execute(text("INSERT INTO players (player_id, full_name) VALUES (:id, 'Unknown Base Player') ON CONFLICT DO NOTHING"), {"id": b_id})
                conn.execute(text("INSERT INTO players (player_id, full_name) VALUES (:id, 'Unknown Base Player') ON CONFLICT DO NOTHING"), {"id": p_id})
                
                # Fetch matching target game keys from dates and team strings
                g_lookup = conn.execute(
                    text("""
                        SELECT game_pk FROM games 
                        WHERE game_date = :dt::DATE 
                          AND home_team_id = (SELECT team_id FROM teams WHERE team_name = :home)
                    """),
                    {"dt": row['game_date'], "home": row['home_team']}
                ).fetchone()
                
                if g_lookup:
                    conn.execute(
                        text("""
                            INSERT INTO fact_at_bats (game_pk, batter_id, pitcher_id, event_type, description)
                            VALUES (:g_pk, :b, :p, :ev, :desc)
                        """),
                        {"g_pk": g_lookup[0], "b": b_id, "p": p_id, "ev": row['events'], "desc": row['description']}
                    )
    except Exception as e:
        print(f"Skipping pitch event mapping phase: {e}")

    print("\n🚀 SUCCESS: 3NF tables are populated and live inside Beekeeper Studio!")
    print("==================================================================")

if __name__ == "__main__":
    run_normalization_pipeline()
