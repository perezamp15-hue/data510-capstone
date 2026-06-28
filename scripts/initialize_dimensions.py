import sys
import requests
from datetime import datetime
from sqlalchemy import text
from db_client import get_engine

def seed_static_dimensions():
    print("Seeding static dimensional parameters...")
    engine = get_engine()
    
    with engine.begin() as conn:
        # 1. Teams Sync
        print("Synchronizing master team entities...")
        url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
        teams = requests.get(url).json().get('teams', [])
        for t in teams:
            conn.execute(text("""
                INSERT INTO teams (team_id, abbreviation, team_name, city, nickname, league, division)
                VALUES (:id, :abbrev, :name, :city, :nickname, :league, :div)
                ON CONFLICT (team_id) DO UPDATE SET
                    abbreviation = EXCLUDED.abbreviation, team_name = EXCLUDED.team_name,
                    league = EXCLUDED.league, division = EXCLUDED.division;
            """), {
                "id": t['id'], "abbrev": t.get('fileCode', ''), "name": t['name'],
                "city": t.get('locationName', ''), "nickname": t.get('teamName', ''),
                "league": t.get('league', {}).get('name', ''), "div": t.get('division', {}).get('name', '')
            })

        # 2. Venues Sync
        # 2. Venues Sync (Upgraded for deep metadata extraction!)
        print("Synchronizing master park profiles with full environmental data...")
        url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
        venues = requests.get(url).json().get('venues', [])
        
        for v in venues:
            park_id = v['id']
            park_name = v['name']
            
            # Default values if field lookups fail
            lat, lon, elev, surface, roof = None, None, None, None, None
            
            # Hit the individual venue endpoint to grab the missing details
            try:
                detail_url = f"https://statsapi.mlb.com/api/v1/venues/{park_id}"
                v_detail = requests.get(detail_url).json().get('venues', [{}])[0]
                
                # Dig through the response keys safely
                lat = v_detail.get('location', {}).get('latitude')
                lon = v_detail.get('location', {}).get('longitude')
                elev = v_detail.get('location', {}).get('elevation')
                surface = v_detail.get('fieldInfo', {}).get('surfaceType')
                roof = v_detail.get('fieldInfo', {}).get('roofType')
            except Exception as e:
                # Fallback gently if a venue profile is missing details
                pass

            conn.execute(text("""
                INSERT INTO parks (park_id, park_name, latitude, longitude, elevation, surface_type, roof_style)
                VALUES (:id, :name, :lat, :lon, :elev, :surface, :roof)
                ON CONFLICT (park_id) DO UPDATE SET
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    elevation = EXCLUDED.elevation,
                    surface_type = EXCLUDED.surface_type,
                    roof_style = EXCLUDED.roof_style;
            """), {
                "id": park_id, "name": park_name, "lat": lat, "lon": lon, 
                "elev": elev, "surface": surface, "roof": roof
            })

        # 3. Players Initial Load
        print("Fetching operational baseline players framework...")
        for season in [2023, 2024, 2025, 2026]:
            url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
            people = requests.get(url).json().get('people', [])
            for p in people:
                debut_str = p.get('mlbDebutDate')
                debut_date = datetime.strptime(debut_str, "%Y-%m-%d").date() if debut_str else None
                birth_str = p.get('birthDate')
                birth_date = datetime.strptime(birth_str, "%Y-%m-%d").date() if birth_str else None
                
                conn.execute(text("""
                    INSERT INTO players (player_id, full_name, current_team_id, position_code, bats, throws, birth_date, height, weight, mlb_debut, is_active)
                    VALUES (:id, :name, :team, :pos, :bats, :throws, :birth, :height, :weight, :debut, :active)
                    ON CONFLICT (player_id) DO UPDATE SET is_active = EXCLUDED.is_active;
                """), {
                    "id": p['id'], "name": p['fullName'], "team": p.get('currentTeam', {}).get('id'),
                    "pos": p.get('primaryPosition', {}).get('code', 'UNK'), "bats": p.get('batSide', {}).get('code', 'U'),
                    "throws": p.get('pitchHand', {}).get('code', 'U'), "birth": birth_date, "height": p.get('height', ''),
                    "weight": p.get('weight', None), "debut": debut_date, "active": p.get('active', True)
                })
    print("Static dimensions seed sequence completed.")

if __name__ == "__main__":
    seed_static_dimensions()
