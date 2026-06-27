import pandas as pd
from scripts.db_client import get_engine, fetch_api_json

def run():
    print("Scraping static major league park baselines...")
    url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
    data = fetch_api_json(url)
    
    parks = []
    for v in data.get("venues", []):
        parks.append({
            "park_id": v.get("id"),
            "name": v.get("name"),
            "latitude": v.get("location", {}).get("latitude"),
            "longitude": v.get("location", {}).get("longitude"),
            "elevation": v.get("location", {}).get("elevation"),
            "surface": None,      # Requires manual supplemental modeling
            "roof_type": None
        })
        
    if parks:
        pd.DataFrame(parks).to_sql('parks', get_engine(), if_exists='replace', index=False)
        print("Ballparks base records configured.")

if __name__ == '__main__':
    run()
