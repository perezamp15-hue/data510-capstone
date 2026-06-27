import pandas as pd
from curl_cffi import requests
from io import StringIO

def fetch_statcast_park_factors(season: int = 2026):
    """
    Scrapes the official Statcast Park Factors directly from Baseball Savant.
    If the current season's data is not yet available, falls back to the previous year.
    """
    url = f"https://baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=year&year={season}&stat=index_woba&condition=All&rolling=no&csv=true"
    
    park_factors = {}
    response = requests.get(url, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"Error fetching Park Factors for season {season}. Status: {response.status_code}")
        return park_factors

    csv_data = StringIO(response.text)
    
    # BULLETPROOF FALLBACK LOGIC
    try:
        df = pd.read_csv(csv_data)
        
        # If the CSV parsed but has zero rows of data (empty 2026 dataset)
        if df.empty:
            raise ValueError("Empty Dataframe")
            
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError):
        print(f"No valid CSV data found for {season} (Savant may not have populated it yet).")
        print(f"Fallback triggered: Attempting to pull {season - 1} park factors instead...")
        
        # Step back exactly one year to prevent infinite loops
        if season == 2026:
            return fetch_statcast_park_factors(season=season - 1)
        return park_factors
    
    # Process the valid dataframe
    for _, row in df.iterrows():
        raw_venue = row.get('venue_id')
        if pd.isna(raw_venue):
            continue 
            
        venue_id = int(raw_venue)
        
        park_factors[venue_id] = {
            "venue_id": venue_id,
            "stadium_name": row.get('venue_name'),
            "run_factor": int(row.get('index_run', 100)),
            "singles_factor": int(row.get('index_1b', 100)),
            "doubles_factor": int(row.get('index_2b', 100)),
            "triples_factor": int(row.get('index_3b', 100)),
            "hr_factor": int(row.get('index_hr', 100))
        }
        
    return park_factors
