import os
import sys
import psycopg2
from datetime import datetime, date, timedelta
from psycopg2.extras import execute_values


# =======================================================
# CORE IMPORTS (Ensure these match your file structure)
# =======================================================
from src.scrapers.scrape_stadium_registry import fetch_mlb_stadiums
from src.scrapers.scrape_players import fetch_team_roster
from src.scrapers.scrape_schedule import fetch_season_schedule
from src.scrapers.scrape_environmental_weather import fetch_environmental_weather
from src.scrapers.scrape_pitch_by_pitch import fetch_game_pitch_by_pitch
from src.scrapers.scrape_player_fatigue import estimate_player_fatigue
from src.scrapers.scrape_catcher_framing import fetch_catcher_framing_metrics
from src.scrapers.scrape_park_factors import fetch_statcast_park_factors

def get_db_connection():
    return psycopg2.connect(os.environ["DATABASE_PUBLIC_URL"])

def run_pipeline(season: int, target_date: datetime):
    """
    Main orchestration function to run the daily data pipeline.
    """
    conn = get_db_connection()
    try:
        print(f"--- Starting Pipeline for Season: {season} | Target Date: {target_date.date()} ---")
        
        # 1. Update Park Factors (Phase 4 Fix)
        print("Fetching Park Factors...")
        park_factors = fetch_statcast_park_factors(season=season)
        if park_factors:
            with conn.cursor() as cur:
                for venue_id, data in park_factors.items():
                    cur.execute("""
                        INSERT INTO park_factors (venue_id, season, run_factor, singles_factor, doubles_factor, triples_factor, hr_factor, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (venue_id, season) DO UPDATE SET
                            run_factor = EXCLUDED.run_factor,
                            singles_factor = EXCLUDED.singles_factor,
                            doubles_factor = EXCLUDED.doubles_factor,
                            triples_factor = EXCLUDED.triples_factor,
                            hr_factor = EXCLUDED.hr_factor,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (venue_id, season, data['run_factor'], data['singles_factor'], data['doubles_factor'], data['triples_factor'], data['hr_factor']))
        
        # 2. Update Catcher Framing (Phase 4 Fix)
        print("Fetching Catcher Framing Metrics...")
        catcher_metrics = fetch_catcher_framing_metrics(season=season)
        if catcher_metrics:
            with conn.cursor() as cur:
                for pid, data in catcher_metrics.items():
                    cur.execute("""
                        INSERT INTO catcher_metrics (player_id, season, framing_runs, strike_percentage, pop_time, caught_stealing_pct, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (player_id, season) DO UPDATE SET
                            framing_runs = EXCLUDED.framing_runs,
                            strike_percentage = EXCLUDED.strike_percentage,
                            pop_time = EXCLUDED.pop_time,
                            caught_stealing_pct = EXCLUDED.caught_stealing_pct,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (pid, season, data['framing_runs'], data['strike_percentage'], data.get('pop_time'), data.get('caught_stealing_pct')))

        # 3. Calculate Player Fatigue with Corrected Time-Travel Logic
        print("Calculating Player Fatigue Profiles...")
        with conn.cursor() as cur:
            cur.execute("SELECT player_id FROM players WHERE status_code = 'A';")
            all_active_players = [row[0] for row in cur.fetchall()]

        for player_id in all_active_players:
            # PASSING THE TARGET DATE IN INSTEAD OF RELYING ON SYSTEM CLOCK
            fatigue = estimate_player_fatigue(conn, player_id, season=season, target_date=target_date)
            
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

#  Correct Way: Forcing the pipeline to look at "yesterday"
if __name__ == "__main__":
    # Default to current season if not provided
    target_year = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    
    # If a specific date string is passed via CLI, use it; otherwise, default to yesterday
    if len(sys.argv) > 2:
        run_date = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    else:
        # Subtracting 1 day handles the UTC rollover safely, but we keep it as a full datetime object!
        run_date = datetime.today() - timedelta(days=1)

    # run_date is now a datetime object, so calling .date() inside run_pipeline won't crash
    run_pipeline(season=target_year, target_date=run_date)
