import pandas as pd
import requests

def fetch_statcast_park_factors(season: int = 2026):
    """
    Scrapes the official Statcast Park Factors directly from Baseball Savant.
    Returns a dictionary of stadiums mapped to their component multipliers.
    
    A value of 100 is neutral. 105 means 5% more frequent than league average.
    """
    # Savant's underlying custom park factor endpoint
    url = f"https://baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=year&year={season}&stat=index_woba&condition=All&rolling=no&csv=true"
    
    response = requests.get(url)
    park_factors = {}
    
    if response.status_code != 200:
        print(f"Error fetching Park Factors for season {season}")
        return park_factors

    # Since Savant handles data natively as a CSV stream on this endpoint,
    # we can read it directly using Pandas into a clean dataframe
    from io import StringIO
    csv_data = StringIO(response.text)
    df = pd.read_csv(csv_data)
    
    for _, row in df.iterrows():
        # Clean venue name or map it to your stadium identifiers
        venue_id = int(row.get('venue_id'))
        
        park_factors[venue_id] = {
            "venue_id": venue_id,
            "stadium_name": row.get('venue_name'),
            # --- Specific Hit Component Multipliers ---
            "run_factor": int(row.get('index_run', 100)),
            "singles_factor": int(row.get('index_1b', 100)),
            "doubles_factor": int(row.get('index_2b', 100)),
            "triples_factor": int(row.get('index_3b', 100)),
            "hr_factor": int(row.get('index_hr', 100))
        }
        
    return park_factors
