import sys
import requests
from sqlalchemy import text
from scripts.db_client import get_engine

def seed_static_dimensions():
    print("Initializing Database Master Dimensions (Phase 1)...")
    engine = get_engine()
    
    with engine.begin() as conn:
        print("Fetching and syncing MLB Teams...")
        url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
        data = requests.get(url).json()
        for team in data.get('teams', []):
            conn.execute(text("""
                INSERT INTO teams (team_id, team_name, abbreviation, location)
                VALUES (:id, :name, :abbrev, :loc)
                ON CONFLICT (team_id) DO UPDATE SET 
                    team_name = EXCLUDED.team_name, 
                    abbreviation = EXCLUDED.abbreviation;
            """), {
                "id": team['id'], "name": team['name'], 
                "abbrev": team.get('fileCode', ''), "loc": team.get('locationName', '')
            })

        print("Fetching and syncing MLB Venues...")
        url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
        venue_data = requests.get(url).json()
        for venue in venue_data.get('venues', []):
            conn.execute(text("""
                INSERT INTO parks (park_id, park_name, location)
                VALUES (:id, :name, :loc)
                ON CONFLICT (park_id) DO NOTHING;
            """), {
                "id": venue['id'], "name": venue['name'], "loc": venue.get('city', '')
            })

        print("Initializing baseline player dimension profiles...")
        for season in [2023, 2024, 2025, 2026]:
            url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
            player_data = requests.get(url).json()
            for p in player_data.get('people', []):
                conn.execute(text("""
                    INSERT INTO players (player_id, full_name, primary_position)
                    VALUES (:id, :name, :pos)
                    ON CONFLICT (player_id) DO NOTHING;
                """), {
                    "id": p['id'], "name": p['fullName'], 
                    "pos": p.get('primaryPosition', {}).get('code', 'UNK')
                })

    print("Master Dimension seeding completed successfully!")

if __name__ == "__main__":
    seed_static_dimensions()
