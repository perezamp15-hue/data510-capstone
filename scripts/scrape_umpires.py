import sys
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date):
    print(f"Syncing game officials and umpires matrix for: {target_date}")
    engine = get_engine()
    
    # 1. Fetch all games for that date from our internal database
    with engine.connect() as conn:
        result = conn.execute(text("SELECT game_pk FROM games WHERE game_date = :date"), {"date": target_date})
        game_pks = [row[0] for row in result.fetchall()]
        
    if not game_pks:
        print("No games found in database for this date window.")
        return

    print(f"Processing boxscore officials arrays for {len(game_pks)} games...")
    
    for pk in game_pks:
        boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            box_data = fetch_api_json(boxscore_url)
            officials = box_data.get('officials', [])
            
            with engine.begin() as txn_conn:
                for off in officials:
                    official_info = off.get('official', {})
                    umpire_id = int(official_info.get('id'))
                    umpire_name = official_info.get('fullName')
                    position = off.get('officialType') # Home Plate, First Base, etc.
                    
                    # Ensure the master umpire row registry exists
                    txn_conn.execute(text("""
                        INSERT INTO umpires (umpire_id, umpire_name)
                        VALUES (:ump_id, :name)
                        ON CONFLICT (umpire_id) DO UPDATE SET umpire_name = EXCLUDED.umpire_name;
                    """), {"ump_id": umpire_id, "name": umpire_name})
                    
                    # Note: If your schema uses an umpire_assignments linkage table, map it here.
                    # Otherwise, this populates your base umpire table safely.
                    
        except Exception as e:
            print(f"Skipping game {pk} due to boxscore lookup error: {e}")
            continue
            
    print("Umpires lookup verification completed.")

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-06-22"
    run(date_arg)
