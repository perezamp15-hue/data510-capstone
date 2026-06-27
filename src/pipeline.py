import os
import sys
from datetime import date, datetime, timedelta

# =======================================================
# PATH IMMUNITY SAFEGUARDS (Must execute first)
# =======================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
SRC_DIR = os.path.join(BASE_DIR, "src")                               

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# =======================================================
# CORE IMPORTS
# =======================================================
import psycopg2
from psycopg2.extras import execute_values

# Master Import Matrix matching your exact repository files
from src.scrapers.scrape_stadium_registry import fetch_mlb_stadiums
from src.scrapers.scrape_schedule import fetch_season_schedule
from src.scrapers.scrape_players import fetch_team_roster
from src.scrapers.scrape_park_factors import fetch_park_factors
from src.scrapers.scrape_catcher_framing import fetch_catcher_framing_metrics
from src.scrapers.scrape_environmental_weather import fetch_environmental_weather
from src.scrapers.scrape_pitch_by_pitch import fetch_game_pitch_by_pitch
from src.scrapers.scrape_boxscore import fetch_boxscore_data
from src.scrapers.scrape_injuries import fetch_injury_reports
from src.scrapers.scrape_bullpen import fetch_bullpen_metrics
from src.scrapers.scrape_defensive_quality import fetch_defensive_quality
from src.scrapers.scrape_team_trends import fetch_team_trends
from src.scrapers.scrape_umpire_trends import fetch_umpire_trends
from src.scrapers.scrape_player_fatigue import estimate_player_fatigue
from src.scrapers.scrape_baserunning import fetch_baserunning_metrics

# Splits & Lineups
from src.scrapers.scrape_batter_splits import fetch_batter_splits       # Matching typo file name
from src.scrapers.scraper_player_splits import fetch_player_splits
from src.scrapers.scrape_pitcher_platoon_splits import fetch_pitcher_platoon_splits
from src.scrapers.scrape_pitcher_season import fetch_pitcher_season_stats
from src.scrapers.scrape_batter_statcast import fetch_batter_statcast_metric
from src.scrapers.scrape_batter_vs_pitch_type import fetch_batter_vs_pitch_type
from src.scrapers.scrape_batter_vs_pitcher import fetch_batter_vs_pitcher
from src.scrapers.scrape_battar_lineup_position import fetch_lineup_positions

def get_db_connection():
    """Establishes connection to the Postgres warehouse using environment variables."""
    return psycopg2.connect(
        dbname=os.getenv("DATABASE_PUBLIC_URL") or os.getenv("PGDATABASE") or "mlb_simulator",
        user=os.getenv("PGUSER") or "postgres",
        password=os.getenv("PGPASSWORD") or "postgres",
        host=os.getenv("PGHOST") or "localhost",
        port=os.getenv("PGPORT") or "5432"
    )

def run_pipeline(season: int):
    print(f"\n--- Starting Global ETL Pipeline Sequence for Season {season} ---")
    conn = get_db_connection()
    
    try:
        # =======================================================
        # PHASE 1: STATIC & GLOBAL ENVIRONMENT MATRIX
        # =======================================================
        print("\n[PHASE 1] Ingesting Stadium Registries & Park Factors...")
        stadiums_data = fetch_mlb_stadiums(season=season)
        if stadiums_data:
            with conn.cursor() as cur:
                for s in stadiums_data:
                    cur.execute("""
                        INSERT INTO stadiums (venue_id, stadium_name, city, state_abbrev, latitude, longitude, timezone_offset)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (venue_id) DO UPDATE SET stadium_name = EXCLUDED.stadium_name;
                    """, (s["venue_id"], s["stadium_name"], s["city"], s["state"], s["latitude"], s["longitude"], s["timezone_offset"]))
        
        park_factors = fetch_park_factors(season=season)
        if park_factors:
            with conn.cursor() as cur:
                for team_id, factors in park_factors.items():
                    cur.execute("""
                        INSERT INTO team_park_factors (team_id, season, runs_factor, hr_factor)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (team_id, season) DO UPDATE SET runs_factor = EXCLUDED.runs_factor;
                    """, (team_id, season, factors.get("runs"), factors.get("hr")))
        
        print("Synchronizing Master Schedule Matrix...")
        schedule_games = fetch_season_schedule(season=season)
        if schedule_games:
            with conn.cursor() as cur:
                for g in schedule_games:
                    cur.execute("""
                        INSERT INTO schedule (game_pk, season, game_date, home_team_id, away_team_id, venue_id, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_pk) DO UPDATE SET status = EXCLUDED.status;
                    """, (g["game_pk"], g["season"], g["game_date"], g["home_team_id"], g["away_team_id"], g["venue_id"], g["status"]))
        conn.commit()

        # =======================================================
        # PHASE 2: DAILY LEAGUE-WIDE UPDATES (Non-Game Specific)
        # =======================================================
        print("\n[PHASE 2] Updating League Injury Reports...")
        injuries = fetch_injury_reports()
        if injuries:
            with conn.cursor() as cur:
                # Clear yesterday's snapshot to maintain an active injury report
                cur.execute("TRUNCATE TABLE active_injuries;")
                execute_values(cur, """
                    INSERT INTO active_injuries (player_id, player_name, injury_status, notes)
                    VALUES %s;
                """, [(inj["player_id"], inj["name"], inj["status"], inj["notes"]) for inj in injuries])
        
        print("Compiling Team Trends, Defensive Quality, & Umpires...")
        with conn.cursor() as cur:
            # Query active team ids to populate trend metrics
            cur.execute("SELECT DISTINCT home_team_id FROM schedule WHERE season = %s;", (season,))
            team_ids = [row[0] for row in cur.fetchall() if row[0]]
            
            for t_id in team_ids:
                # Defensive Matrix
                def_q = fetch_defensive_quality(team_id=t_id, season=season)
                if def_q:
                    cur.execute("""
                        INSERT INTO team_defense (team_id, season, drs, oaa) VALUES (%s, %s, %s, %s)
                        ON CONFLICT (team_id, season) DO UPDATE SET drs = EXCLUDED.drs;
                    """, (t_id, season, def_q.get("drs"), def_q.get("oaa")))
                
                # Rolling Momentum Projections
                trends = fetch_team_trends(team_id=t_id, season=season)
                for window, stats in trends.items():
                    if stats:
                        cur.execute("""
                            INSERT INTO team_rolling_trends (team_id, season, rolling_window, runs_per_game, ops, pitching_era)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (team_id, season, rolling_window) DO UPDATE SET ops = EXCLUDED.ops;
                        """, (t_id, season, window, stats.get("runs_per_game"), stats.get("ops"), stats.get("pitching_era")))
        conn.commit()

        # =======================================================
        # PHASE 3: TARGETED YESTERDAY GAME HYDRO-STREAM
        # =======================================================
        yesterday_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"\n[PHASE 3] Filtering completed game datasets for yesterday ({yesterday_str})...")
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT game_pk FROM schedule 
                WHERE status = 'Final' AND season = %s AND game_date = %s;
            """, (season, yesterday_str))
            completed_games = [row[0] for row in cur.fetchall()]

        if not completed_games:
            print("No finalized games found for yesterday. Skipping pitch tracking ingestion.")
        else:
            for game_pk in completed_games:
                print(f"  🎮 Hydrating game metric profiles for game_pk: {game_pk}")
                weather = fetch_environmental_weather(conn, game_pk)
                boxscore = fetch_boxscore_data(conn, game_pk)
                pitches = fetch_game_pitch_by_pitch(conn, game_pk)
                
                if pitches:
                    with conn.cursor() as cur:
                        pitch_rows = [
                            (p["play_event_id"], game_pk, p["pitcher_id"], p["batter_id"], 
                             p["pitch_type"], p["velocity"], p["exit_velocity"], p["launch_angle"], p["result"])
                            for p in pitches
                        ]
                        execute_values(cur, """
                            INSERT INTO pitch_trajectories (play_event_id, game_pk, pitcher_id, batter_id, pitch_type, velocity, exit_velocity, launch_angle, result)
                            VALUES %s ON CONFLICT (play_event_id) DO NOTHING;
                        """, pitch_rows)
            conn.commit()

        # =======================================================
        # PHASE 4: PLAYER SPLITS & DERIVED MATRICES
        # =======================================================
        print("\n[PHASE 4] Updating Statcast Performance, Splits & Lineup Registries...")
        catcher_framing = fetch_catcher_framing_metrics(season=season)
        bullpen_relief = fetch_bullpen_metrics(season=season)
        baserunning = fetch_baserunning_metrics(season=season)
        
        with conn.cursor() as cur:
            cur.execute("SELECT player_id, position_code FROM players;")
            player_directory = {row[0]: row[1] for row in cur.fetchall()}

        print(f"  Syncing split profiles and fatigue coefficients for {len(player_directory)} players...")
        
        dt_target = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())

        for idx, (player_id, pos_code) in enumerate(player_directory.items()):
            # Safe status logs
            if idx % 300 == 0 and idx > 0:
                print(f"     Processed {idx} individual biological assets...")

            # Fatigue Indexes tracking layer
            fatigue = estimate_player_fatigue(conn, player_id, season=season, target_date=dt_target)
            if fatigue:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO player_fatigue_biometrics (player_id, season, execution_date, travel_distance_7d, sleep_quality_index)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (player_id, season, execution_date) DO UPDATE SET sleep_quality_index = EXCLUDED.sleep_quality_index;
                    """, (player_id, season, yesterday_str, fatigue.get("travel_distance_last_7_days"), fatigue.get("sleep_quality_index")))

            # Split evaluation steps branching by position profile assignments
            if pos_code == "1":  # Pitchers
                pitch_season = fetch_pitcher_season_stats(player_id, season=season)
                pitch_platoon = fetch_pitcher_platoon_splits(player_id, season=season)
                # (Execute updates for specialized pitching tables here)
            else:  # Position Players
                bat_splits = fetch_batter_splits(player_id, season=season)
                generic_splits = fetch_player_splits(player_id, season=season, group="hitting")
                statcast_profile = fetch_batter_statcast_metric(player_id, season=season)
                # (Execute updates for specialized batting tables here)

        conn.commit()
        print("\nGlobal Pipeline execution cycle completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nPipeline crashed during transaction sequence: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    # Fallback directly to 2026 for simulation contexts if terminal args are empty
    target_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    run_pipeline(target_year)

