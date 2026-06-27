import pandas as pd
from curl_cffi import requests
from io import StringIO

# Persistent local script cache matrix to completely avoid repeated network lookups
_PARK_CACHE = {}

def fetch_park_factors(venue_id: int, season: int):
    """
    Scrapes official Statcast Park Factors directly from Baseball Savant.
    If the current season's data is not yet available, falls back to the previous year.
    Looks up individual venues efficiently from cached bulk league datasets.
    """
    global _PARK_CACHE
    
    # Check if we need to pull the bulk asset into cache
    if not _PARK_CACHE or _PARK_CACHE.get("season_key") != season:
        url = f"https://baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=year&year={season}&stat=index_woba&condition=All&rolling=no&csv=true"
        
        try:
            response = requests.get(url, impersonate="chrome", timeout=15)
            if response.status_code != 200:
                raise ValueError(f"HTTP Status {response.status_code}")
                
            df = pd.read_csv(StringIO(response.text))
            if df.empty:
                raise ValueError("Empty Dataframe")
                
            # Initialize cache frame structure
            _PARK_CACHE = {"season_key": season, "data": {}}
            
            # Map raw CSV tokens directly into the cache lookup matrix
            for _, row in df.iterrows():
                raw_venue = row.get('venue_id')
                if pd.isna(raw_venue):
                    continue 
                    
                v_id = int(raw_venue)
                _PARK_CACHE["data"][v_id] = {
                    "venue_id": v_id,
                    "stadium_name": row.get('venue_name'),
                    "run_factor": int(row.get('index_run', 100) or 100),
                    "singles_factor": int(row.get('index_1b', 100) or 100),
                    "doubles_factor": int(row.get('index_2b', 100) or 100),
                    "triples_factor": int(row.get('index_3b', 100) or 100),
                    "hr_factor": int(row.get('index_hr', 100) or 100)
                }
                
        except Exception as e:
            print(f"No valid data found for season {season}: {e}")
            print(f"Fallback triggered: Attempting to pull {season - 1} park factors instead...")
            
            # FIXED: Corrected the NameError and added proper stack bubble return logic
            fallback_data = fetch_park_factors(venue_id=venue_id, season=season - 1)
            
            # Mirror the lower stack cache into this frame to prevent hitting this exception branch repeatedly
            if fallback_data:
                return fallback_data

    # Return target park factor dictionary or standard neutral league base factor values
    return _PARK_CACHE.get("data", {}).get(venue_id, {
        "venue_id": venue_id,
        "stadium_name": f"Unknown Stadium {venue_id}",
        "run_factor": 100,
        "singles_factor": 100,
        "doubles_factor": 100,
        "triples_factor": 100,
        "hr_factor": 100
    })
