import os
import sys

# =======================================================
# PATH IMMUNITY SAFEGUARDS (Must execute first)
# =======================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Maps to /app
SRC_DIR = os.path.join(BASE_DIR, "src")                               # Maps to /app/src

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# =======================================================
# CORE IMPORTS
# =======================================================
import psycopg2
from datetime import date, timedelta
from psycopg2.extras import execute_values

# Absolute sub-package imports reflecting your exact GitHub filenames
from src.scrapers.scrape_stadium_registry import fetch_mlb_stadiums
from src.scrapers.scrape_players import fetch_team_roster
from src.scrapers.scrape_schedule import fetch_season_schedule
from src.scrapers.scrape_environmental_weather import fetch_environmental_weather
# Imported from scrape_boxscore per your renamed commit notes
from src.scrapers.scrape_pitch_by_pitch import fetch_game_pitch_by_pitch
from src.scrapers.scrape_player_fatigue import estimate_player_fatigue
from src.scrapers.scrape_catcher_framing import fetch_catcher_framing_metrics

def get_db_connection():
    return psycopg2.connect(os.environ["DATABASE_PUBLIC_URL"])

def run_pipeline(season: int):
    """Executes the complete database sync structured down the relational dependency waterfall."""
    print("Connecting to Postgres Warehouse...")
    conn = get_db_connection()
    
    try:
        # =======================================================
        # PHASE 1: MASTER REFERENCE INGESTION (No Foreign Keys)
        # =======================================================
        print(f"Phase 1: Syncing Stadium Master Registry for {season}...")
        stadiums_data = fetch_mlb_stadiums(season=season)

# Remove duplicate venue_ids
        unique_stadiums = {}

        for stadium in stadiums_data:
            unique_stadiums[stadium["venue_id"]] = stadium

        stadiums_data = list(unique_stadiums.values())
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO stadiums (venue_id, stadium_name, city, state, country, latitude, longitude, timezone_offset)
                VALUES %s ON CONFLICT (venue_id) DO UPDATE SET 
                    stadium_name = EXCLUDED.stadium_name, timezone_offset = EXCLUDED.timezone_offset;
            """, [(s['venue_id'], s['stadium_name'], s['city'], s['state'], s['country'], s['latitude'], s['longitude'], s['timezone_offset']) for s in stadiums_data])
        conn.commit()

        # =======================================================
        # PHASE 2: SCHEDULES & ROSTERS
        # =======================================================
        print("Phase 2: Syncing Schedule Matrix...")
        schedule_games = fetch_season_schedule(season=season)
        with conn.cursor() as cur:
            execute_values(cur, """
                INSERT INTO schedule (game_pk, season, game_date, home_team_id, away_team_id, home_team_name, away_team_name, venue_id, status)
                VALUES %s ON CONFLICT (game_pk) DO UPDATE SET status = EXCLUDED.status;
            """, [(g['game_pk'], g['season'], g['game_date'], g['home_team_id'], g['away_team_id'], g['home_team_name'], g['away_team_name'], g['venue_id'], g['status']) for g in schedule_games])
        conn.commit()

        # =======================================================
        # PHASE 3: GAME METADATA, WEATHER, & TRACKING (Yesterday's Games)
        # =======================================================
        yesterday_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"Phase 3: Hydrating completed game datasets for yesterday ({yesterday_str})...")
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT game_pk 
                FROM schedule 
                WHERE status = 'Final' 
                  AND season = %s 
                  AND game_date = %s;
            """, (season, yesterday_str))
            completed_games = [row[0] for row in cur.fetchall()]

        if not completed_games:
            print("No finalized games found for yesterday. Skipping pitch ingestion.")
        else:
            for game_pk in completed_games:
                weather = fetch_environmental_weather(conn, game_pk)
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO environmental_weather (game_pk, temperature, condition_description, wind_speed_mph, wind_direction)
                        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (game_pk) DO NOTHING;
                    """, (weather['game_pk'], weather['temperature'], weather['condition_description'], weather['wind_speed_mph'], weather['wind_direction']))
                
                # Executes function out of your newly assigned scrape_boxscore layout
                pitches = fetch_game_pitch_by_pitch(conn, game_pk)
                if pitches:
                    with conn.cursor() as cur:
                        execute_values(cur, """
                            INSERT INTO pitch_by_pitch (play_event_id, game_pk, pitcher_id, batter_id, pitch_type, velocity, exit_velocity, launch_angle, result)
                            VALUES %s ON CONFLICT (play_event_id) DO NOTHING;
                        """, [(p['play_event_id'], p['game_pk'], p['pitcher_id'], p['batter_id'], p['pitch_type'], p['velocity'], p['exit_velocity'], p['launch_angle'], p['result']) for p in pitches])
                conn.commit()

        # =======================================================
        # PHASE 4: PLAYER ANALYTICS & DERIVED FATIGUE MODELS
        # =======================================================
        print("Phase 4: Compiling individual performance trends & fatigue coefficients...")
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT player_id FROM players;")
            all_active_players = [row[0] for row in cur.fetchall()]

        for player_id in all_active_players:
            fatigue = estimate_player_fatigue(conn, player_id, season=season)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO batter_fatigue (player_id, consecutive_games_played, travel_distance_last_7_days, sleep_quality_index, rest_days_last_14_days, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (player_id) DO UPDATE SET
                        consecutive_games_played = EXCLUDED.consecutive_games_played,
                        travel_distance_last_7_days = EXCLUDED.travel_distance_last_7_days,
                        sleep_quality_index = EXCLUDED.sleep_quality_index,
                        rest_days_last_14_days = EXCLUDED.rest_days_last_14_days,
                        updated_at = CURRENT_TIMESTAMP;
                """, (fatigue['player_id'], fatigue['consecutive_games_played'], fatigue['travel_distance_last_7_days'], fatigue['sleep_quality_index'], fatigue['rest_days_last_14_days']))
        conn.commit()

        print("Pipeline execution cycle completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"Pipeline crashed during transaction sequence: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    target_year = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    run_pipeline(target_year)
