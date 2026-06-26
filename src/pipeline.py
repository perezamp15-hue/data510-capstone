import os
import sys
import psycopg2
from datetime import date
from psycopg2.extras import execute_values

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# --- reference scrapers---
from scrapers.scrape_stadium_registry import fetch_mlb_stadiums
from scrapers.scrape_players import fetch_team_roster
from scrapers.scrape_schedule import fetch_season_schedule

# ---contextual and analytical scrapers---
from scrapers.scrape_environmental_weather import fetch_environmental_weather
from scrapers.scrape_pitch_by_pitch import fetch_game_pitch_by_pitch
from scrapers.scrape_player_fatigue import estimate_player_fatigue
from scrapers.scrape_catcher_framing import fetch_catcher_framing_metrics

def get_db_connection():
    """Establishes connection to the Postgres warehouse using Railway environment variables."""
    return psycopg2.connect(
        dbname=os.getenv("DATABASE_PUBLIC_URL") or os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT")
    )

def run_pipeline(season: int):
    """Executes the complete database sync structured down the relational dependency waterfall."""
    print(f"Connecting to Postgres Warehouse...")
    conn = get_db_connection()
    
    try:
        # =======================================================
        # PHASE 1: MASTER REFERENCE INGESTION (No Foreign Keys)
        # =======================================================
        print(f"Phase 1: Syncing Stadium Master Registry for {season}...")
        stadiums_data = fetch_mlb_stadiums(season=season)
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
        print(f"Phase 2: Syncing Schedule Matrix...")
        schedule_games = fetch_season_schedule(season=season)
        with conn.cursor() as cur:
            # We filter incoming schedule data to match valid stadiums already captured
            execute_values(cur, """
                INSERT INTO schedule (game_pk, season, game_date, home_team_id, away_team_id, home_team_name, away_team_name, venue_id, status)
                VALUES %s ON CONFLICT (game_pk) DO UPDATE SET status = EXCLUDED.status;
            """, [(g['game_pk'], g['season'], g['game_date'], g['home_team_id'], g['away_team_id'], g['home_team_name'], g['away_team_name'], g['venue_id'], g['status']) for g in schedule_games])
        conn.commit()

        # =======================================================
        # PHASE 3: GAME METADATA, WEATHER, & TRACKING (Pitch-by-Pitch)
        # =======================================================
        print(f"Phase 3: Hydrating completed game datasets...")
        # Pull games from the DB that are finalized but lack weather tracking records
        with conn.cursor() as cur:
            cur.execute("SELECT game_pk FROM schedule WHERE status = 'Final' AND season = %s;", (season,))
            completed_games = [row[0] for row in cur.fetchall()]

        for game_pk in completed_games:
            # Weather updates utilize dynamic roof checking inside the script
            weather = fetch_environmental_weather(conn, game_pk)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO environmental_weather (game_pk, temperature, condition_description, wind_speed_mph, wind_direction)
                    VALUES (%s, %s, %s, %s, %s) ON CONFLICT (game_pk) DO NOTHING;
                """, (weather['game_pk'], weather['temperature'], weather['condition_description'], weather['wind_speed_mph'], weather['wind_direction']))
            
            # Trajectory timeline streams (automates player registration on rookie discoveries)
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
        print(f"Phase 4: Compiling individual performance trends & fatigue coefficients...")
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT player_id FROM players;")
            all_active_players = [row[0] for row in cur.fetchall()]

        for player_id in all_active_players:
            # Fatigue estimations leverage dynamic DB geo-coordinates lookups
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
    # Fallback default configuration maps runtime smoothly to the current calendar year
    target_year = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    run_pipeline(target_year)
