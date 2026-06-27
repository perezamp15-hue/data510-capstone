import sys
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date):
    print(f"Syncing wide game officials matrix for: {target_date}")
    engine = get_engine()
    
    # 1. Fetch all games for that date
    with engine.connect() as conn:
        result = conn.execute(text("SELECT game_pk FROM games WHERE game_date = :date"), {"date": target_date})
        game_pks = [row[0] for row in result.fetchall()]
        
    if not game_pks:
        print("No games found in database for this date window.")
        return

    print(f"Processing boxscore wide rows for {len(game_pks)} games...")
    
    for pk in game_pks:
        boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            box_data = fetch_api_json(boxscore_url)
            officials = box_data.get('officials', [])
            
            # Dictionary to map umpire IDs to your specific wide columns
            ump_row = {
                "game_pk": pk,
                "home_plate": None,
                "first_base": None,
                "second_base": None,
                "third_base": None
            }
            
            with engine.begin() as txn_conn:
                for off in officials:
                    official_info = off.get('official', {})
                    umpire_id = int(official_info.get('id'))
                    umpire_name = official_info.get('fullName')
                    position = off.get('officialType') # "Home Plate", "First Base", etc.
                    
                    # STEP A: Always update your master registry so the names exist
                    txn_conn.execute(text("""
                        INSERT INTO umpires (umpire_id, umpire_name)
                        VALUES (:ump_id, :name)
                        ON CONFLICT (umpire_id) DO UPDATE SET umpire_name = EXCLUDED.umpire_name;
                    """), {"ump_id": umpire_id, "name": umpire_name})
                    
                    # STEP B: Route the ID to the correct column slot
                    if position == "Home Plate":
                        ump_row["home_plate"] = umpire_id
                    elif position == "First Base":
                        ump_row["first_base"] = umpire_id
                    elif position == "Second Base":
                        ump_row["second_base"] = umpire_id
                    elif position == "Third Base":
                        ump_row["third_base"] = umpire_id

                # STEP C: Write the compiled side-by-side row into game_umpires
                txn_conn.execute(text("""
                    INSERT INTO game_umpires (game_pk, home_plate_ump_id, first_base_ump_id, second_base_ump_id, third_base_ump_id)
                    VALUES (:game_pk, :home_plate, :first_base, :second_base, :third_base)
                    ON CONFLICT (game_pk) DO UPDATE SET 
                        home_plate_ump_id = EXCLUDED.home_plate_ump_id,
                        first_base_ump_id = EXCLUDED.first_base_ump_id,
                        second_base_ump_id = EXCLUDED.second_base_ump_id,
                        third_base_ump_id = EXCLUDED.third_base_ump_id;
                """), ump_row)
                    
        except Exception as e:
            print(f"Skipping game {pk} due to parsing issue: {e}")
            continue
            
    print("Game Umpires wide matrix successfully synced.")

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-06-22"
    run(date_arg)
