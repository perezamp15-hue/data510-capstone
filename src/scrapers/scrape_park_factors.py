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

    # --- NEW: Check if Savant returned an HTML error/blank page instead of a CSV ---
    if "venue_id" not in response.text:
        print(f"Baseball Savant did not return CSV data for {season}.")
        print(f"Savant Response Snippet: {response.text[:100].strip()}...")
        print(f"Fallback triggered: Attempting to pull {season - 1} park factors instead...")
        
        # Prevent infinite loops, but step back one year
        if season == 2026:
            return fetch_statcast_park_factors(season=season - 1)
        return park_factors

    csv_data = StringIO(response.text)
    
    try:
        df = pd.read_csv(csv_data)
    except pd.errors.ParserError:
        print(f"Failed to parse Park Factors CSV. Baseball Savant may have blocked the request.")
        return park_factors
    
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
