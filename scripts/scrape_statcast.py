import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(start_date=None, end_date=None):
    if not start_date or not end_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        yesterday = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = start_date or yesterday
        end_date = end_date or yesterday

    print(f"Pulling Statcast streams between {start_date} and {end_date}...")
    
    # URL structure targeting the standard pybaseball/Statcast CSV endpoint
    url = f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt={start_date}&game_date_lt={end_date}"
    
    try:
        # Load csv data directly into dataframe
        df = pd.read_csv(url, low_memory=False)
        
        if df.empty:
            print("No Statcast data found for this date range.")
            return

        # DEFENSIVE FIX: Convert common logic evaluation flags to standard booleans and fill NAs
        # This completely resolves the "boolean value of NA is ambiguous" error
        if 'is_strike' in df.columns:
            df['is_strike'] = df['is_strike'].fillna(False).astype(bool)
        if 'is_ball' in df.columns:
            df['is_ball'] = df['is_ball'].fillna(False).astype(bool)
            
        # Clean up global NaN traces for safe DB ingestion
        df = df.replace({np.nan: None})
        
        engine = get_engine()
        
        # Pull valid game keys to verify tracking parameters
        try:
            valid_g_pks = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        except Exception:
            valid_g_pks = []

        # Example filtration step down to valid matches
        if valid_g_pks and 'game_pk' in df.columns:
            df = df[df['game_pk'].isin(valid_g_pks)]

        if df.empty:
            print("Statcast data retrieved, but no matching games found in internal database.")
            return

        # (Insert your specific internal tracking/saving loops to statcast_pitches table here)
        # ...
        
        print(f"Statcast data processed cleanly for {len(df)} rows.")
        
    except Exception as e:
        print(f"Statcast failed: {e}")
        # Soft-fail or re-raise based on orchestrator structure. We raise here to catch it transparently.
        raise e

if __name__ == "__main__":
    s_date = sys.argv[1] if len(sys.argv) > 1 else None
    e_date = sys.argv[2] if len(sys.argv) > 2 else s_date
    run(s_date, e_date)
