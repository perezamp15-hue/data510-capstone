import sys
from datetime import datetime, timedelta

try:
    import scripts.scrape_game_feed as scrape_game_feed
    import scripts.scrape_statcast as scrape_statcast
    import scripts.scrape_transactions as scrape_transactions
except ModuleNotFoundError as e:
    print(f"\nCRITICAL ENTRY INITIALIZATION PATHWAYS MISSING: {e}")
    sys.exit(1)

def run_pipeline_for_date(target_date):
    print(f"\n=======================================================")
    print(f"Running Normalized 7-Table Warehouse System: {target_date}")
    print(f"=======================================================")

    print("\n--- Phase 2: Running Game Feeds ---")
    try:
        scrape_game_feed.run(target_date)
    except Exception as e:
        print(f"Core game schedule execution failed: {e}")
        return

    print("\n--- Phase 3: Telemetry Stream Logging ---")
    try:
        scrape_statcast.run(target_date, target_date)
    except Exception as e:
        print(f"Statcast execution failed: {e}")
        
    try:
        scrape_transactions.run(target_date)
    except Exception as e:
        print(f"Transaction ingestion processing failed: {e}")

    print(f"\nPipeline step successful for date: {target_date}")

if __name__ == "__main__":
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    date_arg = sys.argv[1] if len(sys.argv) > 1 else yesterday
    run_pipeline_for_date(date_arg)
