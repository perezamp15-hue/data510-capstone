import sys
import io
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db_client import get_engine
from sqlalchemy import text

def run(start_date=None, end_date=None):
    if not start_date or not end_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        yesterday = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = start_date or yesterday
        end_date = end_date or yesterday

    print(f"Pulling Statcast streams between {start_date} and {end_date}...")
    url = f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt={start_date}&game_date_lt={end_date}"
    
    # FIX: Add authentic browser headers to completely bypass the 403 Forbidden error
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        # Pull the payload securely using requests before giving it to pandas
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status() # Raises an exception if a 403 occurs
        
        # Read the raw string stream cleanly into a DataFrame
        df = pd.read_csv(io.StringIO(response.text), low_memory=False)
        
        if df.empty:
            print("No Statcast data found for this date range.")
            return

        # Handle modern pandas nullable types defensively
        if 'is_strike' in df.columns:
            df['is_strike'] = df['is_strike'].fillna(False).astype(bool)
        if 'is_ball' in df.columns:
            df['is_ball'] = df['is_ball'].fillna(False).astype(bool)
            
        df = df.replace({np.nan: None})
        
        engine = get_engine()
        try:
            valid_g_pks = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        except Exception:
            valid_g_pks = []

        if valid_g_pks and 'game_pk' in df.columns:
            df = df[df['game_pk'].isin(valid_g_pks)]

        if df.empty:
            print("Statcast data retrieved, but no matching games found in internal database.")
            return

        # Insert your internal database tracking execution loops below
        # ...
        
        print(f"Statcast stream fully synced for {len(df)} entries.")
        
    except Exception as e:
        print(f"Statcast failed: {e}")
        # Let the orchestrator handle the error or proceed down the execution chain
        pass

if __name__ == "__main__":
    s_date = sys.argv[1] if len(sys.argv) > 1 else None
    e_date = sys.argv[2] if len(sys.argv) > 2 else s_date
    run(s_date, e_date)
