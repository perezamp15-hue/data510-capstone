import sys
import pandas as pd
from db_client import get_engine, fetch_api_json

def run(season=2026):
    url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
    data = fetch_api_json(url)
    
    players = []
    for p in data.get("people", []):
        players.append({
            "player_id": p.get("id"),
            "name": p.get("fullName"),
            "DOB": p.get("birthDate"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "bats": p.get("batSide", {}).get("code"),
            "throws": p.get("pitchHand", {}).get("code"),
            "debut": p.get("mlbDebutDate")
        })
        
    if players:
        df = pd.DataFrame(players)
        # Use clean upsert logic for structural tables
        df.to_sql('players', get_engine(), if_exists='replace', index=False)
        print("Rosters base snapshot updated.")

if __name__ == '__main__':
    run()
