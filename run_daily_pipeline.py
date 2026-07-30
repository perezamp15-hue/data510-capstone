import subprocess
import sys
from datetime import datetime, timedelta

try:
    import scripts.scrape_game_feed as scrape_game_feed
    import scripts.scrape_statcast as scrape_statcast
    import scripts.scrape_transactions as scrape_transactions
except ModuleNotFoundError as e:
    print(f"\nCRITICAL ENTRY INITIALIZATION PATHWAYS MISSING: {e}")
    sys.exit(1)

# PHASE ONE ANALYTICS FOUNDATION
def run_analytics_foundation() -> None:
    """Run optional validation only when its module exists."""
    from importlib.util import find_spec

    if find_spec("analytics.run_phase_one") is None:
        print("Analytics foundation module is not installed; skipping Phase 4.")
        return

    print("\n" + "=" * 70)
    print("Running Phase One Analytics Foundation")
    print("=" * 70)

    result = subprocess.run(
        [sys.executable, "-m", "analytics.run_phase_one"],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Analytics foundation validation failed.")

    print("Analytics foundation completed successfully.")

# DAILY PIPELINE
def run_pipeline_for_date(target_date: str) -> None:
    print("\n=======================================================")
    print(f"Running Normalized 7-Table Warehouse System: {target_date}")
    print("=======================================================")

    # GAME FEED INGESTION
    print("\n--- Phase 1: Running Game Feeds ---")

    try:
        scrape_game_feed.run(target_date)
        print("Game feed ingestion completed.")
    except Exception as e:
        print(f"Core game schedule execution failed: {e}")
        return

    # STATCAST INGESTION
    print("\n--- Phase 2: Running Statcast Collection ---")

    try:
        scrape_statcast.run(target_date, target_date)
        print("Statcast ingestion completed.")
    except Exception as e:
        print(f"Statcast execution failed: {e}")

    # TRANSACTIONS INGESTION
    print("\n--- Phase 3: Running Transactions Collection ---")

    try:
        scrape_transactions.run(target_date)
        print("Transaction ingestion completed.")
    except Exception as e:
        print(f"Transaction ingestion processing failed: {e}")

    # ANALYTICS FOUNDATION
    print("\n--- Phase 4: Running Analytics Foundation ---")

    try:
        run_analytics_foundation()
    except Exception as e:
        print(f"Analytics foundation failed: {e}")
        return

    print("\n=======================================================")
    print(f"Pipeline completed successfully for {target_date}")
    print("=======================================================")

# ENTRY POINT
if __name__ == "__main__":
    yesterday = (
        datetime.now() - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    date_arg = sys.argv[1] if len(sys.argv) > 1 else yesterday

    run_pipeline_for_date(date_arg)
