import pandas as pd
from curl_cffi import requests # <-- Import this instead of standard requests or cloudscraper
from io import StringIO

def fetch_statcast_park_factors(season: int = 2026):
    """
    Scrapes the official Statcast Park Factors directly from Baseball Savant.
    """
    url = f"https://baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=year&year={season}&stat=index_woba&condition=All&rolling=no&csv=true"
    
    park_factors = {}
    
    # MAGIC FIX: Impersonate a real Chrome browser's network signature!
    response = requests.get(url, impersonate="chrome")
    
    if response.status_code != 200:
        print(f"Error fetching Park Factors for season {season}. Status: {response.status_code}")
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
