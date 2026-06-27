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
    """Reshapes raw data from the games table to fill team_games and team_schedule rows dynamically."""
    print(f"Processing team performance data rollups for {target_date}...")
    engine = get_engine()
    
    with engine.begin() as conn:
        # Fetch the games recorded for this date
        query = text("""
            SELECT game_pk, season, home_team_id, away_team_id, home_score, away_score, game_type
            FROM games WHERE game_date = :date
        """)
        games = conn.execute(query, {"date": target_date}).fetchall()
        
        for g in games:
            pk, season, home_id, away_id, h_score, a_score, g_type = g
            
            # Handle null fields for upcoming or unplayed matches
            h_score = h_score if h_score is not None else 0
            a_score = a_score if a_score is not None else 0
            
            # Populate team_schedule entries
            for team_id, opponent_id, is_home in [(home_id, away_id, True), (away_id, home_id, False)]:
                conn.execute(text("""
                    INSERT INTO team_schedule (game_pk, season, team_id, opponent_id, is_home, game_type)
                    VALUES (:pk, :season, :team_id, :opp_id, :is_home, :g_type)
                    ON CONFLICT (game_pk, team_id) DO NOTHING;
                """), {"pk": pk, "season": season, "team_id": team_id, "opp_id": opponent_id, "is_home": is_home, "g_type": g_type})
            
            # Calculate wins and losses for completed games
            home_won = h_score > a_score
            away_won = a_score > h_score
            
            # Populate team_games entries
            conn.execute(text("""
                INSERT INTO team_games (game_pk, team_id, runs_scored, runs_allowed, is_winner)
                VALUES (:pk, :team_id, :scored, :allowed, :winner)
                ON CONFLICT (game_pk, team_id) DO UPDATE SET is_winner = EXCLUDED.is_winner;
            """), {"pk": pk, "team_id": home_id, "scored": h_score, "allowed": a_score, "winner": home_won})
            
            conn.execute(text("""
                INSERT INTO team_games (game_pk, team_id, runs_scored, runs_allowed, is_winner)
                VALUES (:pk, :team_id, :scored, :allowed, :winner)
                ON CONFLICT (game_pk, team_id) DO UPDATE SET is_winner = EXCLUDED.is_winner;
            """), {"pk": pk, "team_id": away_id, "scored": a_score, "allowed": h_score, "winner": away_won})
            
    print("Downstream team performance matrices generated successfully.")

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=5)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    print("--- Phase 1: Syncing Core Indices ---")
    try:
        run_strict_script("scrape_teams.py")
        run_strict_script("scrape_park_info.py")
        run_strict_script("scrape_schedule.py", "2026")
        run_strict_script("scrape_rosters.py")
    except subprocess.CalledProcessError:
        sys.exit(1)

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
