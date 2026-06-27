import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, 'scripts')
docker_scripts_dir = "/app/scripts"

for path in [scripts_dir, docker_scripts_dir, base_dir]:
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)

print("--- Docker Container Path Debugger ---")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Calculated Scripts Dir:    {scripts_dir} (Exists: {os.path.exists(scripts_dir)})")
print(f"Files inside /app/scripts: {os.listdir(docker_scripts_dir) if os.path.exists(docker_scripts_dir) else 'Folder not found'}")
print("--------------------------------------")

try:
    import scrape_teams
    import scrape_park_info
    import scrape_rosters
    import scrape_schedule
    import scrape_game_feed
    import scrape_statcast
    import scrape_lineups
    import scrape_defense
    import scrape_bullpen
    import scrape_weather
    import scrape_umpires
    import scrape_pitch_arsenal
    import scrape_transactions
    from db_client import get_engine  # Needed to verify data states
    from sqlalchemy import text
except ModuleNotFoundError as e:
    print(f"\nCRITICAL IMPORT ERROR: {e}")
    sys.exit(1)

from datetime import datetime, timedelta
import pytz

def check_and_seed_database(season=2026):
    """Checks if foundational tables are empty and automatically self-seeds if true."""
    print("\n--- Pre-Flight Constraint Validation ---")
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            team_count = conn.execute(text("SELECT COUNT(*) FROM public.teams;")).scalar()
            park_count = conn.execute(text("SELECT COUNT(*) FROM public.parks;")).scalar()
            game_count = conn.execute(text("SELECT COUNT(*) FROM public.games;")).scalar()
            
        if team_count == 0 or park_count == 0 or game_count == 0:
            print("Empty database ecosystem detected! Initiating automated structural recovery sequence...")
            
            print("System-Seed Step 1/4: Ingesting professional baseball team identities...")
            scrape_teams.run()
            
            print("System-Seed Step 2/4: Populating major league venue dimensions and parks...")
            scrape_park_info.run()
            
            print("System-Seed Step 3/4: Creating master seasonal schedule structural framework...")
            scrape_schedule.run(season=season)
            
            print("System-Seed Step 4/4: Constructing initial active structural player rosters...")
            scrape_rosters.run(season=season)
            
            print("Structural database verification complete. All lookups and dimensions are intact.")
        else:
            print(f"Foundation verified (Teams: {team_count}, Parks: {park_count}, Master Framework Games: {game_count}). Processing incremental ingestion normally.")
            
    except Exception as e:
        print(f"Pre-flight safety execution bypassed due to warning: {e}. Attempting direct processing...")

def run_pipeline_for_date(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        # Defaults to 5 days ago for clean historical backfill windows
        target_date = (datetime.now(local_tz) - timedelta(days=5)).strftime('%Y-%m-%d')
        
    print(f"\n=========================================")
    print(f"RUNNING CRON-READY PIPELINE FOR: {target_date}")
    print(f"=========================================\n")
    
    # Run the self-healing layout check first
    check_and_seed_database(season=2026)

    # -------------------------------------------------------------
    # PHASE 1: CORE INDEXES & CONSTRAINTS
    # -------------------------------------------------------------
    print("\n--- Phase 1: Syncing Core Indices ---")
    try: 
        scrape_teams.run()
    except Exception as e: 
        print(f"Teams sync failed: {e}")
        
    try: 
        scrape_park_info.run()
    except Exception as e: 
        print(f"Parks sync failed: {e}")

    try: 
        scrape_schedule.run(season=2026)
    except Exception as e: 
        print(f"Schedule sync failed: {e}")
        
    try: 
        scrape_rosters.run(season=2026)
    except Exception as e: 
        print(f"Roster sync failed: {e}")

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
