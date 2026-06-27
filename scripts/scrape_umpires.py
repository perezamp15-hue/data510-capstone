import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    engine = get_engine()
    try: 
        valid_games = pd.read_sql("SELECT game_pk FROM games WHERE game_date = %s", con=engine, params=(target_date,))['game_pk'].tolist()
    except Exception: 
        return
        
    all_umps = {}
    assignments = []
    
    for pk in valid_games:
        # Hit the direct boxscore path rather than the live feed
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            data = fetch_api_json(url)
            # The official array lives directly under the root dictionary block here
            officials = data.get('officials', [])
            
            assign = {"game_pk": pk, "home_plate_ump_id": None, "first_base_ump_id": None, "second_base_ump_id": None, "third_base_ump_id": None}
            
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
            
    if not assignments: return
    
    with engine.begin() as conn:
        # 1. Update master directory mapping table
        for u_id, u_name in all_umps.items():
            conn.execute(text("""
                INSERT INTO umpires (umpire_id, umpire_name) 
                VALUES (:u_id, :u_name) 
                ON CONFLICT (umpire_id) DO UPDATE SET umpire_name = EXCLUDED.umpire_name;
            """), {"u_id": u_id, "u_name": u_name})
            
        # 2. Wire the game configurations together
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
    print(f"Umpire arrays mapped successfully for date: {target_date}")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
