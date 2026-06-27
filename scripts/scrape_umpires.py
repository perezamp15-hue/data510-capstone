import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    engine = get_engine()
    
    print("Scanning database for games missing umpire profiles...")
    try:
        # Pulls any historical games in your system lacking tracking entries in game_umpires
        query = """
            SELECT g.game_pk 
            FROM games g
            LEFT JOIN game_umpires gu ON g.game_pk = gu.game_pk
            WHERE gu.game_pk IS NULL
            LIMIT 50;
        """
        valid_games = pd.read_sql(query, con=engine)['game_pk'].tolist()
        
        if not valid_games:
            print("Database Status: All existing games already have umpire profiles mapped!")
            return
            
        print(f"Found {len(valid_games)} games ready to capture umpire assignments.")
    except Exception as e:
        print(f"Database cross-reference failed: {e}")
        return
        
    all_umps = {}
    assignments = []
    
    for pk in valid_games:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            data = fetch_api_json(url)
            officials = data.get('officials', [])
            
            assign = {
                "game_pk": int(pk), 
                "home_plate_ump_id": None, 
                "first_base_ump_id": None, 
                "second_base_ump_id": None, 
                "third_base_ump_id": None
            }
            
            for official in officials:
                pos = official.get('officialType')
                u_node = official.get('official', {})
                u_id = u_node.get('id')
                name = u_node.get('fullName')
                
                if not u_id or not name: continue
                
                all_umps[int(u_id)] = name
                if pos == 'Home Plate': assign['home_plate_ump_id'] = int(u_id)
                elif pos == 'First Base': assign['first_base_ump_id'] = int(u_id)
                elif pos == 'Second Base': assign['second_base_ump_id'] = int(u_id)
                elif pos == 'Third Base': assign['third_base_ump_id'] = int(u_id)
                
            assignments.append(assign)
        except Exception:
            continue
            
    if not assignments: 
        print("No official umpire configurations found inside game boxscores.")
        return
    
    with engine.begin() as conn:
        for u_id, u_name in all_umps.items():
            conn.execute(text("""
                INSERT INTO umpires (umpire_id, umpire_name) 
                VALUES (:u_id, :u_name) 
                ON CONFLICT (umpire_id) DO UPDATE SET umpire_name = EXCLUDED.umpire_name;
            """), {"u_id": u_id, "u_name": u_name})
            
        for assign in assignments:
            conn.execute(text("""
                INSERT INTO game_umpires (game_pk, home_plate_ump_id, first_base_ump_id, second_base_ump_id, third_base_ump_id)
                VALUES (:game_pk, :home_plate_ump_id, :first_base_ump_id, :second_base_ump_id, :third_base_ump_id)
                ON CONFLICT (game_pk) DO UPDATE SET 
                    home_plate_ump_id = EXCLUDED.home_plate_ump_id, 
                    first_base_ump_id = EXCLUDED.first_base_ump_id, 
                    second_base_ump_id = EXCLUDED.second_base_ump_id, 
                    third_base_ump_id = EXCLUDED.third_base_ump_id;
            """), assign)
    print(f"Umpire assignments successfully written for {len(assignments)} games.")

if __name__ == "__main__":
    run()
