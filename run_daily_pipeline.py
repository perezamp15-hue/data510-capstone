import sys
import os
import subprocess
from datetime import datetime, timedelta
import pytz

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
except ModuleNotFoundError as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

def run_strict_script(script_name, *args):
    """Executes a foundational script; crashes the pipeline immediately if it fails."""
    script_path = os.path.join(scripts_dir, script_name)
    if not os.path.exists(script_path):
        script_path = os.path.join(base_dir, script_name)
        
    cmd = [sys.executable, script_path] + list(args)
    print(f"\n🤖 Running Foundation Script: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=5)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    # -------------------------------------------------------------
    # PHASE 1: STRICT INGESTION LOOKUPS
    # -------------------------------------------------------------
    print("--- Phase 1: Syncing Core Indices ---")
    try:
        run_strict_script("scrape_teams.py")
        run_strict_script("scrape_park_info.py")
        run_strict_script("scrape_schedule.py", "2026")
        run_strict_script("scrape_rosters.py")
        print("Phase 1 lookups complete.")
    except subprocess.CalledProcessError as e:
        print(f"\nPIPELINE HALTED: Core base script failed.")
        sys.exit(1)

    # -------------------------------------------------------------
    # PHASE 2: PRIMARY EVENT INGESTION
    # -------------------------------------------------------------
    print("\n--- Phase 2: Ingesting Daily Game Feeds ---")
    try: 
        scrape_game_feed.run(target_date)
    except Exception as e:
        print(f"CRITICAL ERROR: Main Boxscore Feed failed for {target_date}: {e}")
        return

    # -------------------------------------------------------------
    # PHASE 3: DEPENDENT TELEMETRY & METRICS
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # PHASE 4: OFFICIATING & SUPPLEMENTAL UPDATES
    # -------------------------------------------------------------
    print("\n--- Phase 4: Downstream Aggregations & Officiating ---")
    try:
        # Flexible signature inspection to pass the target date safely
        import inspect
        sig = inspect.signature(scrape_umpires.run)
        if len(sig.parameters) > 0:
            scrape_umpires.run(target_date)
        else:
            scrape_umpires.run()
        print("Umpires pipeline executed successfully.")
    except Exception as e:
        print(f"Umpires sync failed: {e}")
        
    try: 
        scrape_pitch_arsenal.run()
        print("Pitch arsenals recalculated.")
    except Exception as e: 
        print(f"Arsenal update failed: {e}")

    print(f"\nPipeline execution successfully finished for window: {target_date}")

if __name__ == '__main__':
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline_for_date(passed_date)
