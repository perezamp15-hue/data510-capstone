import sys
import os
import subprocess
from datetime import datetime, timedelta
import pytz

base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, 'scripts')
docker_scripts_dir = "/app/scripts"

# Make sure Python knows exactly where to find your files
for path in [scripts_dir, docker_scripts_dir, base_dir]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

print("--- Docker Container Path Debugger ---")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Calculated Scripts Dir:    {scripts_dir}")
print("--------------------------------------")

# Lazy load core modules to minimize runtime execution weight
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
except ModuleNotFoundError as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

def run_isolated_script(script_name, *args):
    """Executes a script as an isolated standalone shell process.
    
    This ensures that each script runs inside its own execution layer, 
    matching terminal call behavior perfectly.
    """
    script_path = os.path.join(scripts_dir, script_name)
    if not os.path.exists(script_path):
        script_path = os.path.join(base_dir, script_name)
        
    cmd = [sys.executable, script_path] + list(args)
    print(f"Spawning Process: {' '.join(cmd)}")
    
    try:
        # Runs the script and automatically pipes output directly to your Railway log terminal
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Process {script_name} encountered an issue. Continuing pipeline execution...")

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=5)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    # -------------------------------------------------------------
    # PHASE 1: CORE INDEXES & CONSTRAINTS (Runs Daily, Safely Skips Existing Rows)
    # -------------------------------------------------------------
    print("--- Phase 1: Syncing Core Indices ---")
    
    # These execute as separate process threads every day. 
    # If the rows exist, your internal DB conflict logic bypasses them automatically.
    run_isolated_script("scrape_teams.py")
    run_isolated_script("scrape_park_info.py")
    run_isolated_script("scrape_schedule.py", "2026")
    run_isolated_script("scrape_rosters.py")

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
