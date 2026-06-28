import os
import sys
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "scripts")))

from datetime import datetime, timedelta
from run_daily_pipeline import run_pipeline_for_date
from scripts.initialize_dimensions import seed_static_dimensions 

def run_backfill(start_date_str, end_date_str):
    try:
        seed_static_dimensions()
    except Exception as e:
        print(f"Critical initialization failure: {e}")
        sys.exit(1)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    current_date = start_date

    print(f"Launching pipeline timeline loop from {start_date_str} to {end_date_str}...")

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        run_pipeline_for_date(date_str)
        current_date += timedelta(days=1)

    print("Backfill completed successfully!")

if __name__ == "__main__":
    run_backfill("2023-03-30", "2026-06-27")
