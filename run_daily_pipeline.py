import sys
from datetime import datetime, timedelta

try:
    import scripts.scrape_game_feed as scrape_game_feed
    import scripts.scrape_statcast as scrape_statcast
    import scripts.scrape_game_context as scrape_game_context  
    import scripts.scrape_transactions as scrape_transactions
    from scripts.db_client import get_engine 
except ModuleNotFoundError as e:
    print(f"\nCRITICAL IMPORT ERROR IN PIPELINE INITIALIZATION: {e}")
    sys.exit(1)

def run_pipeline_for_date(target_date):
    print(f"\n=======================================================")
    print(f"Executing Optimized Warehouse Pipeline: {target_date}")
    print(f"=======================================================")

    # --- Phase 2: Core Scoring Metadata ---
    print("\n--- Phase 2: Ingesting Daily Game Feeds ---")
    try:
        scrape_game_feed.run(target_date)
    except Exception as e:
        print(f"Boxscore Feed failure: {e}")
        return

    # --- Phase 3: Raw Observations & Context ---
    print("\n--- Phase 3: Processing Dependent Telemetry & Context ---")
    
    # 1. Pitch-by-pitch granular tracking data
    try:
        scrape_statcast.run(target_date, target_date)
    except Exception as e:
        print(f"Statcast telemetry pipeline failure: {e}")
    
    # 2. Single hit context aggregator (Weather, Umpires, Defense)
    try:
        scrape_game_context.run(target_date)
    except Exception as e:
        print(f"Consolidated game context processing failure: {e}")
        
    # 3. Dynamic Roster status tracking
    try:
        scrape_transactions.run(target_date)
    except Exception as e:
        print(f"Transactions pipeline logger failure: {e}")

    print(f"\nDaily pipeline step execution successful for date: {target_date}")

if __name__ == "__main__":
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    date_arg = sys.argv[1] if len(sys.argv) > 1 else yesterday
    run_pipeline_for_date(date_arg)
