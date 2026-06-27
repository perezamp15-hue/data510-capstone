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
    
    print(f"Syncing game umpires directly from API schedule for: {target_date}")
    
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}"
    try:
        schedule_data = fetch_api_json(schedule_url)
        dates_node = schedule_data.get('dates', [])
        if not dates_node:
            print(f"No scheduled matches found on API for date: {target_date}")
            return
        valid_games = [g.get('gamePk') for g in dates_node[0].get('games', []) if g.get('gamePk')]
    except Exception as e:
        print(f"Schedule pre-fetch failed: {e}")
        return
        
    all_umps = {}
    assignments = []
    
    for pk in valid_games:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            data = fetch_api_json(url)
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
            
    if not assignments: 
        print("No umpire assignments found in target game payloads.")
        return
    
    engine = get_engine()
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
    print(f"Umpire tables successfully populated for {len(assignments)} games.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
