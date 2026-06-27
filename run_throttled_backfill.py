import sys
import os
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Ensure system paths align
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

try:
    # Import the core execution engine we built in the previous step
    from run_backfill import backfill_pipeline_for_range
except ImportError:
    print("Error: Could not link to run_backfill.py. Ensure both scripts are in the same directory.")
    sys.exit(1)

def run_throttled_campaign(start_str, end_str, break_minutes=15):
    global_start = datetime.strptime(start_str, '%Y-%m-%d')
    global_end = datetime.strptime(end_str, '%Y-%m-%d')
    
    current_chunk_start = global_start
    chunk_index = 1

    print("=================================================================")
    print(f"INITIATING AUTOMATED THROTTLED CAMPAIGN")
    print(f"   Timeline: {start_str} to {end_str}")
    print(f"   Cool-down Interval: {break_minutes} minutes between monthly batches")
    print("=================================================================\n")

    while current_chunk_start <= global_end:
        # Calculate the end of the current monthly block
        # Relativedelta rolls to the next month, minus 1 day caps it perfectly
        current_chunk_end = current_chunk_start + relativedelta(months=1) - timedelta(days=1)
        
        # Guard rail: Don't let the monthly chunk overshoot our grand end-date target
        if current_chunk_end > global_end:
            current_chunk_end = global_end
            
        chunk_start_str = current_chunk_start.strftime('%Y-%m-%d')
        chunk_end_str = current_chunk_end.strftime('%Y-%m-%d')

        print(f"\n[BATCH #{chunk_index}] Processing: {chunk_start_str} ➡️ {chunk_end_str}")
        print("-----------------------------------------------------------------")
        
        # Execute the full monthly block through your pipeline routines
        try:
            backfill_pipeline_for_range(chunk_start_str, chunk_end_str)
            print(f"[BATCH #{chunk_index}] Completed successfully.")
        except Exception as e:
            print(f"Critical interruption during Batch #{chunk_index}: {e}")
            print("Holding execution parameters to prevent cascading pipeline failure.")
            sys.exit(1)

        # Move the pointer to the start of the next calendar block
        current_chunk_start = current_chunk_end + timedelta(days=1)
        chunk_index += 1

        # Only sleep if there are remaining blocks left to process
        if current_chunk_start <= global_end:
            print(f"\nCooling down container engine for {break_minutes} minutes...")
            print(f"   Next block will resume around: {(datetime.now() + timedelta(minutes=break_minutes)).strftime('%H:%M:%S')}")
            time.sleep(break_minutes * 60)

    print("\nAll historical batches processed successfully across the specified range!")

if __name__ == '__main__':
    # Default parameters: Opening Day 2024 through mid-season 2026
    # 15 minute breaks give the database connection pool time to reset completely
    START_TARGET = "2024-03-28"
    END_TARGET = "2026-06-25" 
    COOL_DOWN_MINUTES = 15
    
    run_throttled_campaign(START_TARGET, END_TARGET, COOL_DOWN_MINUTES)
