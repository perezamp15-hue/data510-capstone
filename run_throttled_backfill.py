import sys
import os
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Force the execution directory into Python's lookup path
base_dir = os.path.dirname(os.path.abspath(__file__))
scripts_dir = os.path.join(base_dir, 'scripts')

for path in [base_dir, scripts_dir]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    # Changed from run_backfill to match your exact filename: backfill.py
    import backfill
except ModuleNotFoundError as e:
    print(f"❌ Core File Link Error: {e}")
    print(f"Could not find backfill.py inside directory: {base_dir}")
    sys.exit(1)

def run_throttled_campaign(start_str, end_str, break_minutes=15):
    global_start = datetime.strptime(start_str, '%Y-%m-%d')
    global_end = datetime.strptime(end_str, '%Y-%m-%d')
    
    current_chunk_start = global_start
    chunk_index = 1

    print("=================================================================")
    print(f"🚀 INITIATING AUTOMATED THROTTLED CAMPAIGN")
    print(f"   Timeline: {start_str} to {end_str}")
    print(f"   Cool-down Interval: {break_minutes} minutes between monthly batches")
    print("=================================================================\n")

    while current_chunk_start <= global_end:
        current_chunk_end = current_chunk_start + relativedelta(months=1) - timedelta(days=1)
        if current_chunk_end > global_end:
            current_chunk_end = global_end
            
        chunk_start_str = current_chunk_start.strftime('%Y-%m-%d')
        chunk_end_str = current_chunk_end.strftime('%Y-%m-%d')

        print(f"\n📦 [BATCH #{chunk_index}] Processing: {chunk_start_str} ➡️ {chunk_end_str}")
        print("-----------------------------------------------------------------")
        
        try:
            # Invokes the backend pipeline array handler function
            backfill.backfill_pipeline_for_range(chunk_start_str, chunk_end_str)
            print(f"✅ [BATCH #{chunk_index}] Completed successfully.")
        except Exception as e:
            print(f"❌ Critical interruption during Batch #{chunk_index}: {e}")
            sys.exit(1)

        current_chunk_start = current_chunk_end + timedelta(days=1)
        chunk_index += 1

        if current_chunk_start <= global_end:
            print(f"\n💤 Cooling down container engine for {break_minutes} minutes...")
            time.sleep(break_minutes * 60)

    print("\n🎉 All historical batches processed successfully!")

if __name__ == '__main__':
    START_TARGET = "2024-03-28"
    END_TARGET = "2026-06-25" 
    COOL_DOWN_MINUTES = 15
    
    run_throttled_campaign(START_TARGET, END_TARGET, COOL_DOWN_MINUTES)
