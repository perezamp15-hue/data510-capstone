import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(season=2026):
    print(f"Capturing professional 40-man active player profiles for {season} season...")
    # Pull total rosters using broad sports endpoint matrix
    url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
    try:
        data = fetch_api_json(url)
        people = data.get('people', [])
        parsed = []
        
        # Valid active leagues check mapping
        engine = get_engine()
        valid_teams = pd.read_sql("SELECT team_id FROM teams", con=engine)['team_id'].tolist()
        
        for p in people:
            team_node = p.get('currentTeam', {})
            t_id = team_node.get('id')
            
            # Skip historical/unmapped teams to avoid foreign key errors
            if not t_id or int(t_id) not in valid_teams:
                continue
                
            parsed.append({
                "player_id": int(p.get('id')),
                "full_name": p.get('fullName'),
                "current_team_id": int(t_id),
                "position_code": p.get('primaryPosition', {}).get('code'),
                "bats": p.get('batSide', {}).get('code'),
                "throws": p.get('pitchHand', {}).get('code'),
                "birth_date": p.get('birthDate'),
                "height": p.get('height'),
                "weight": int(p.get('weight')) if p.get('weight') else None,
                "mlb_debut": p.get('mlbDebutDate'),
                "is_active": p.get('active', True)
            })
            
        df = pd.DataFrame(parsed)
        if df.empty: return
        
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO players (player_id, full_name, current_team_id, position_code, bats, throws, birth_date, height, weight, mlb_debut, is_active)
                    VALUES (:player_id, :full_name, :current_team_id, :position_code, :bats, :throws, :birth_date, :height, :weight, :mlb_debut, :is_active)
                    ON CONFLICT (player_id) DO UPDATE SET 
                        full_name = EXCLUDED.full_name, current_team_id = EXCLUDED.current_team_id, position_code = EXCLUDED.position_code,
                        bats = EXCLUDED.bats, throws = EXCLUDED.throws, birth_date = EXCLUDED.birth_date, height = EXCLUDED.height, 
                        weight = EXCLUDED.weight, mlb_debut = EXCLUDED.mlb_debut, is_active = EXCLUDED.is_active;
                """), row.to_dict())
        print(f"Registered {len(df)} player bio snapshots.")
    except Exception as e:
        print(f"Error processing roster sheets: {e}")
