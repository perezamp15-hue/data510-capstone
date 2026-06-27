import pandas as pd
from pybaseball import statcast
from db_client import get_engine

def clean_statcast_data(df):
    """
    Cleans raw pybaseball Statcast data frames to make them safe for SQL insertion.
    """
    if df is None or df.empty:
        return pd.DataFrame()
        
    # 1. Convert timestamp strings to true datetime objects
    if 'game_date' in df.columns:
        df['game_date'] = pd.to_datetime(df['game_date'])
        
    # 2. Convert object columns containing mixed text/numbers to standard strings
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].astype(str).replace('nan', None)
        
    # 3. Replace standard Pandas floating-point NaN allocations with clean database Nulls
    df = df.where(pd.notnull(df), None)
    
    return df

def run(start_date, end_date=None):
    """
    Scrapes pitch-by-pitch Statcast data streams for a date range and saves it to PostgreSQL.
    """
    if end_date is None:
        end_date = start_date
        
    print(f"Fetching Statcast events between {start_date} and {end_date}...")
    
    try:
        # Pull raw metrics using the pybaseball engine wrapper
        raw_data = statcast(start_dt=start_date, end_dt=end_date)
        
        cleaned_data = clean_statcast_data(raw_data)
        
        if cleaned_data.empty:
            print(f"No Statcast data recorded for the period: {start_date} to {end_date}.")
            return
            
        # Ingest straight into your targeted PostgreSQL database instance
        engine = get_engine()
        table_name = "fact_statcast_pitches"
        
        print(f"Writing {len(cleaned_data)} pitch records to database table '{table_name}'...")
        cleaned_data.to_sql(
            name=table_name,
            con=engine,
            if_exists='append',
            index=False,
            chunksize=500 # Stream in batches to prevent container out-of-memory errors
        )
        print("Statcast processing step completed successfully!")
        
    except Exception as e:
        print(f"CRITICAL ERROR gathering Statcast data streams: {e}")
        raise e

if __name__ == '__main__':
    # Test script run for opening week data frame context
    run("2026-04-02", "2026-04-02")
