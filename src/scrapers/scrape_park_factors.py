import pandas as pd
import cloudscraper
from io import StringIO

def fetch_statcast_park_factors(season: int = 2026):
    """
    Scrapes the official Statcast Park Factors directly from Baseball Savant.
    Returns a dictionary of stadiums mapped to their component multipliers.
    """
    url = f"https://baseballsavant.mlb.com/leaderboard/statcast-park-factors?type=year&year={season}&stat=index_woba&condition=All&rolling=no&csv=true"
    
    # FIX 1: Mask the Python scraper as a normal web browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    park_factors = {}
    scraper = cloudscraper.create_scraper()
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching Park Factors for season {season}. Status: {response.status_code}")
        return park_factors

    csv_data = StringIO(response.text)
    
    # FIX 2: Safeguard the pipeline against future Cloudflare HTML blocks
    try:
        df = pd.read_csv(csv_data)
    except pd.errors.ParserError as e:
        print(f"Failed to parse Park Factors CSV. Baseball Savant may have blocked the request.")
        return park_factors
    
    for _, row in df.iterrows():
        # SAFEGUARD: Check for NaN before casting to integer
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
