import time
import subprocess
import os
import sys
from datetime import datetime, timedelta
from run_daily_pipeline import run_pipeline_for_date

# Define your range
start_date = datetime.strptime("2023-03-30", "%Y-%m-%d")
end_date = datetime.strptime("2026-06-25", "%Y-%m-%d")

print("\nLaunching timeline loop. Foundations will sync dynamically per date...\n")

current_date = start_date
day_count = 0

while current_date <= end_date:
    date_str = current_date.strftime("%Y-%m-%d")
    print(f"\nProcessing Date: {date_str}")
    
    try:
        # This function handles the year calculation and index sync dynamically!
        run_pipeline_for_date(date_str)
    except Exception as e:
        print(f"Error on {date_str}, skipping day: {e}")
        
    current_date += timedelta(days=1)
    day_count += 1
    
    # Take a 5-minute cool-down every 30 days to free RAM and reset connection pools
    if day_count % 30 == 0 and current_date <= end_date:
        print(f"\nIngested 30 days. Resting connection pools for 5 minutes...")
        time.sleep(300)

print("Bulk backfill campaign completed successfully!")
