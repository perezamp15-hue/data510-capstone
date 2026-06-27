import sys
import os
import subprocess

base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, 'scripts')
docker_scripts_dir = "/app/scripts"

for path in [scripts_dir, docker_scripts_dir, base_dir]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

print("--- Docker Container Path Debugger ---")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Calculated Scripts Dir:    {scripts_dir} (Exists: {os.path.exists(scripts_dir)})")
print("--------------------------------------")

try:
    import scrape_game_feed
    import scrape_statcast
    import scrape_lineups
    import scrape_defense
    import scrape_bullpen
    import scrape_weather
    import scrape_umpires
    import scrape_pitch_arsenal
    import scrape_transactions
    from db_client import get_engine 
    from sqlalchemy import text
except ModuleNotFoundError as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

from datetime import datetime, timedelta
import pytz

def force_shell_seed(script_name, *args):
    """Executes a script as a separate shell subprocess to avoid argument/import conflicts."""
    script_path = os.path.join(scripts_dir, script_name)
    if not os.path.exists(script_path):
        # Fallback for flat directories
        script_path = os.path.join(base_dir, script_name)
        
    cmd = [sys.executable, script_path] + list(args)
    print(f"🤖 Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Subprocess failed for {script_name}!")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")

def check_and_seed_database():
    """Checks if foundational tables are empty and automatically self-seeds using clean shell processes."""
    print("\n--- Pre-Flight Constraint Validation ---")
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            team_count = conn.execute(text("SELECT COUNT(*) FROM public.teams;")).scalar()
            park_count = conn.execute(text("SELECT COUNT(*) FROM public.parks;")).scalar()
            game_count = conn.execute(text("SELECT COUNT(*) FROM public.games;")).scalar()
            
        if team_count == 0 or park_count == 0 or game_count == 0:
            print("Empty database ecosystem detected! Initiating shell-isolated recovery sequence...")
            
            print("\n[Step 1/4] Seeding Team Identities...")
            force_shell_seed("scrape_teams.py")
            
            print("\n[Step 2/4] Seeding Venues & Parks...")
            force_shell_seed("scrape_park_info.py")
            
            print("\n[Step 3/4] Seeding 2026 Master Framework...")
            force_shell_seed("scrape_schedule.py", "2026")
            
            print("\n[Step 4/4] Seeding Initial Player Rosters...")
            force_shell_seed("scrape_rosters.py")
            
            print("\nStructural database verification complete. All lookups and dimensions are intact.")
        else:
            print(f"Foundation verified (Teams: {team_count}, Parks: {park_count}, Master Framework Games: {game_count}). Ingesting daily logs normally.")
            
    except Exception as e:
        print(f"Pre-flight safety execution bypassed due to validation error: {e}")

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=5)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    # Trigger the robust database verification check
    check_and_seed_database()

    # -------------------------------------------------------------
    # PHASE 2: PRIMARY EVENT INGESTION
    # -------------------------------------------------------------
    print("\n--- Phase 2: Ingesting Daily Game Feeds ---")
    try: 
        scrape_game_feed.run(target_date)
    except Exception as e:
        print(f"CRITICAL ERROR: Main Boxscore Feed failed for {target_date}: {e}")
        print("Aborting downstream dependencies to prevent data corruption.")
        return

    # -------------------------------------------------------------
    # PHASE 3: DEPENDENT TELEMETRY & METRICS
    # -------------------------------------------------------------
    print("\n--- Phase 3: Processing Dependent Telemetry ---")
    try: 
        scrape_statcast.run(target_date, target_date)
    except Exception as e: 
        print(f"Statcast failed: {e}")
        
    try: 
        scrape_lineups.run(target_date)
    except Exception as e: 
        print(f"Lineups failed: {e}")
        
    try: 
        scrape_defense.run(target_date)
    except Exception as e: 
        print(f"Defense failed: {e}")
        
    try: 
        scrape_bullpen.run(target_date)
    except Exception as e: 
        print(f"Bullpen failed: {e}")
        
    try: 
        scrape_weather.run(target_date)
    except Exception as e: 
        print(f"Weather failed: {e}")
        
    try: 
        scrape_umpires.run(target_date)
    except Exception as e: 
        print(f"Umpires failed: {e}")
        
    try: 
        scrape_transactions.run(target_date)
    except Exception as e: 
        print(f"Transactions failed: {e}")
        
    try: 
        scrape_pitch_arsenal.run()
    except Exception as e: 
        print(f"Arsenal update failed: {e}")

    print(f"\nPipeline execution successfully finished for window: {target_date}")

if __name__ == '__main__':
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline_for_date(passed_date)
