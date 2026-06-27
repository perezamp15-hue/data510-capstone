import sys
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date):
    print(f"Syncing game officials matrix for: {target_date}")
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
                    position = off.get('officialType') # e.g., "Home Plate", "First Base"
                    
                    # STEP A: Safely insert/update the master registry table so names are preserved
                    txn_conn.execute(text("""
                        INSERT INTO umpires (umpire_id, umpire_name)
                        VALUES (:ump_id, :name)
                        ON CONFLICT (umpire_id) DO UPDATE SET 
                            umpire_name = EXCLUDED.umpire_name;
                    """), {"ump_id": umpire_id, "name": umpire_name})
                    
                    # STEP B: Safely insert/update the game relationship linkage table
                    txn_conn.execute(text("""
                        INSERT INTO game_umpires (game_pk, umpire_id, umpire_name, position)
                        VALUES (:game_pk, :ump_id, :name, :position)
                        ON CONFLICT (game_pk, umpire_id) DO UPDATE SET 
                            umpire_name = EXCLUDED.umpire_name,
                            position = EXCLUDED.position;
                    """), {
                        "game_pk": pk, 
                        "ump_id": umpire_id, 
                        "name": umpire_name, 
                        "position": position
                    })
                    
        except Exception as e:
            print(f"Skipping game {pk} due to boxscore lookup error: {e}")
            continue
            
    print("Dual-Table Umpire verification completed successfully.")

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-06-22"
    run(date_arg)
