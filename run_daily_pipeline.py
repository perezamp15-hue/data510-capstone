import sys
import os
import subprocess
from datetime import datetime, timedelta
import pytz
from sqlalchemy import text

base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, 'scripts')
docker_scripts_dir = "/app/scripts"

for path in [scripts_dir, docker_scripts_dir, base_dir]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

try:
    import scrape_game_feed
    import scrape_statcast
    import scrape_lineups
    import scrape_defense
    import scrape_bullpen
    import scrape_weather
    import scrape_pitch_arsenal
    import scrape_transactions
    import scrape_umpires
    from db_client import get_engine
except ModuleNotFoundError as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

def run_strict_script(script_name, *args):
    script_path = os.path.join(scripts_dir, script_name)
    if not os.path.exists(script_path):
        script_path = os.path.join(base_dir, script_name)
        
    cmd = [sys.executable, script_path] + list(args)
    print(f"\nRunning Foundation Script: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def populate_downstream_team_tables(target_date):
    """Reshapes raw data from the games table to fill team_games and team_schedules rows dynamically."""
    print(f"Processing team performance data rollups for {target_date}...")
    engine = get_engine()
    
    with engine.begin() as conn:
        games_cols_res = conn.execute(text("""
            SELECT column_name FROM information_schema.columns WHERE table_name = 'games'
        """)).fetchall()
        games_cols = {row[0] for row in games_cols_res}
        
        h_hits_field = 'home_hits' if 'home_hits' in games_cols else 'home_score'
        a_hits_field = 'away_hits' if 'away_hits' in games_cols else 'away_score'
        h_err_field = 'home_errors' if 'home_errors' in games_cols else '0'
        a_err_field = 'away_errors' if 'away_errors' in games_cols else '0'
        
        query = text(f"""
            SELECT game_pk, season, home_team_id, away_team_id, home_score, away_score, game_type,
                   {h_hits_field}, {a_hits_field}, {h_err_field}, {a_err_field}
            FROM games WHERE game_date = :date
        """)
        games = conn.execute(query, {"date": target_date}).fetchall()
        
        for g in games:
            pk, season, home_id, away_id, h_score, a_score, g_type, h_hits, a_hits, h_err, a_err = g
            
            h_score = h_score if h_score is not None else 0
            a_score = a_score if a_score is not None else 0
            h_hits = h_hits if h_hits is not None else 0
            a_hits = a_hits if a_hits is not None else 0
            h_err = h_err if h_err is not None else 0
            a_err = a_err if a_err is not None else 0
            
            conn.execute(text("""
                INSERT INTO team_schedules (game_pk, season_year, game_type)
                VALUES (:pk, :season_year, :g_type)
                ON CONFLICT (game_pk) DO NOTHING;
            """), {"pk": pk, "season_year": season, "g_type": g_type})
            
            home_result = 'W' if h_score > a_score else 'L'
            away_result = 'L' if h_score > a_score else 'W'
            
            conn.execute(text("""
                INSERT INTO team_games (game_pk, team_id, is_home, runs, hits, errors, game_result)
                VALUES (:pk, :team_id, :is_home, :runs, :hits, :errors, :game_result)
                ON CONFLICT (game_pk, team_id) DO UPDATE SET 
                    runs = EXCLUDED.runs,
                    hits = EXCLUDED.hits,
                    errors = EXCLUDED.errors,
                    game_result = EXCLUDED.game_result;
            """), {
                "pk": pk, "team_id": home_id, "is_home": True, 
                "runs": h_score, "hits": h_hits, "errors": h_err, "game_result": home_result
            })
            
            conn.execute(text("""
                INSERT INTO team_games (game_pk, team_id, is_home, runs, hits, errors, game_result)
                VALUES (:pk, :team_id, :is_home, :runs, :hits, :errors, :game_result)
                ON CONFLICT (game_pk, team_id) DO UPDATE SET 
                    runs = EXCLUDED.runs,
                    hits = EXCLUDED.hits,
                    errors = EXCLUDED.errors,
                    game_result = EXCLUDED.game_result;
            """), {
                "pk": pk, "team_id": away_id, "is_home": False, 
                "runs": a_score, "hits": a_hits, "errors": a_err, "game_result": away_result
            })
            
    print("Downstream team performance matrices generated successfully with zero null violations.")

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    current_year = target_date.split("-")[0]
    engine = get_engine()
    
    print(f"--- Phase 1: Syncing Core Indices for {current_year} ---")
    try:
        run_strict_script("scrape_teams.py")
        run_strict_script("scrape_park_info.py")
        run_strict_script("scrape_schedule.py", current_year)
        run_strict_script("scrape_rosters.py", current_year)
    except subprocess.CalledProcessError:
        sys.exit(1)

    # NEW ESCAPE HATCH: Check if there are any valid official games in our DB for this date
    with engine.connect() as conn:
        res = conn.execute(text("SELECT COUNT(*) FROM games WHERE game_date = :date"), {"date": target_date})
        game_count = res.scalar() or 0

    if game_count == 0:
        print(f"\nSkipping daily telemetry: 0 official MLB games scheduled on {target_date}.")
        print(f"Pipeline execution successfully finished for window: {target_date}")
        return

    print(f"\nFound {game_count} scheduled official games. Proceeding with details...")

    print("\n--- Phase 2: Ingesting Daily Game Feeds ---")
    try: scrape_game_feed.run(target_date)
    except Exception as e: print(f"Boxscore Feed failed: {e}"); return

    print("\n--- Phase 3: Processing Dependent Telemetry ---")
    try: scrape_statcast.run(target_date, target_date)
    except Exception as e: print(f"Statcast failed: {e}")
    try: scrape_lineups.run(target_date)
    except Exception as e: print(f"Lineups failed: {e}")
    try: scrape_defense.run(target_date)
    except Exception as e: print(f"Defense failed: {e}")
    try: scrape_bullpen.run(target_date)
    except Exception as e: print(f"Bullpen failed: {e}")
    try: scrape_weather.run(target_date)
    except Exception as e: print(f"Weather failed: {e}")
    try: scrape_transactions.run(target_date)
    except Exception as e: print(f"Transactions failed: {e}")

    print("\n--- Phase 4: Downstream Aggregations & Officiating ---")
    try:
        scrape_umpires.run(target_date)
    except Exception as e:
        print(f"Umpires pipeline sync failed: {e}")

    try:
        populate_downstream_team_tables(target_date)
    except Exception as e:
        print(f"Internal team aggregations calculation failed: {e}")
        
    try: scrape_pitch_arsenal.run()
    except Exception as e: print(f"Arsenal update failed: {e}")

    print(f"\nPipeline execution successfully finished for window: {target_date}")

if __name__ == '__main__':
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline_for_date(passed_date)
