import requests
from datetime import datetime
from sqlalchemy import text
from db_client import get_engine

def run(season):
    print(f"Pre-seeding master player profiles for the {season} season...")
    engine = get_engine()
    
    url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
    players = requests.get(url).json().get('people', [])
    
    if not players:
        print(f"No player data returned for season {season}.")
        return

    with engine.begin() as conn:
        for p in players:
            b_date = p.get('birthDate')
            d_date = p.get('mlbDebutDate')
            
            birth_date = datetime.strptime(b_date, "%Y-%m-%d").date() if b_date else None
            debut_date = datetime.strptime(d_date, "%Y-%m-%d").date() if d_date else None

            conn.execute(text("""
                INSERT INTO public.players (
                    player_id, full_name, current_team_id, position_code, 
                    bats, throws, birth_date, height, weight, mlb_debut, is_active
                ) VALUES (
                    :id, :name, :team_id, :pos, :bats, :throws, :birth, :height, :weight, :debut, :active
                ) ON CONFLICT (player_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    current_team_id = EXCLUDED.current_team_id,
                    position_code = EXCLUDED.position_code,
                    bats = EXCLUDED.bats,
                    throws = EXCLUDED.throws,
                    birth_date = EXCLUDED.birth_date,
                    height = EXCLUDED.height,
                    weight = EXCLUDED.weight,
                    mlb_debut = EXCLUDED.mlb_debut,
                    is_active = EXCLUDED.is_active;
            """), {
                "id": p['id'], "name": p.get('fullName', 'Unknown Player'), "team_id": p.get('currentTeam', {}).get('id'),
                "pos": p.get('primaryPosition', {}).get('code'), "bats": p.get('batSide', {}).get('code'),
                "throws": p.get('pitchHand', {}).get('code'), "birth": birth_date, "height": p.get('height'),
                "weight": p.get('weight'), "debut": debut_date, "active": p.get('active', True)
            })
    print(f"Cleanly synced player profiles for {season}.")
