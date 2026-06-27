import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def extract_umpires_for_game(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
    try:
        data = fetch_api_json(url)
        live_data = data.get('liveData', {})
        boxscore = live_data.get('boxscore', {})
        officials = boxscore.get('officials', [])
        
        # We will collect umpire entities to populate our master directory
        master_umpires = []
        
        # Footprint for this specific game assignment linking IDs
        assignment_record = {
            "game_pk": game_pk,
            "hp_umpire_id": None,
            "ump_1b_id": None,
            "ump_2b_id": None,
            "ump_3b_id": None
        }
        
        for official in officials:
            position = official.get('officialType')
            official_node = official.get('official', {})
            ump_id = official_node.get('id')
            name = official_node.get('fullName')
            
            if not ump_id or not name:
                continue
                
            # Add to master collection list
            master_umpires.append({"umpire_id": int(ump_id), "umpire_name": name})
            
            # Map assignment slots based on positions returned by the API
            if position == 'Home Plate': 
                assignment_record['hp_umpire_id'] = int(ump_id)
            elif position == 'First Base': 
                assignment_record['ump_1b_id'] = int(ump_id)
            elif position == 'Second Base': 
                assignment_record['ump_2b_id'] = int(ump_id)
            elif position == 'Third Base': 
                assignment_record['ump_3b_id'] = int(ump_id)
                
        return master_umpires, assignment_record
        
    except Exception as e:
        print(f"Skipping umpire lookup for game {game_pk}: {e}")
        return [], None

def run(target_date):
    print(f"Gathering relational umpire profiles for date: {target_date}...")
    engine = get_engine()
    
    try:
        valid_games = pd.read_sql(
            "SELECT game_pk FROM games WHERE game_date = %s", 
            con=engine, 
            params=(target_date,)
        )['game_pk'].tolist()
    except Exception as e:
        print(f"Date filter query error, checking total master indices: {e}")
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()

    if not valid_games:
        print(f"No game master records exist in the database for {target_date}.")
        return

    all_umpires_directory = {}
    game_assignments = []
    
    for pk in valid_games:
        master_list, assignment = extract_umpires_for_game(pk)
        if assignment:
            game_assignments.append(assignment)
            for ump in master_list:
                all_umpires_directory[ump['umpire_id']] = ump['umpire_name']
                
    if not game_assignments:
        print("No official crew assignments extracted.")
        return

    # Step 1: Upsert into the Master Umpires dimension table first 
    print(f"Synchronizing {len(all_umpires_directory)} master umpire directory profiles...")
    with engine.begin() as conn:
        for ump_id, ump_name in all_umpires_directory.items():
            conn.execute(text("""
                INSERT INTO umpires (umpire_id, umpire_name)
                VALUES (:umpire_id, :umpire_name)
                ON CONFLICT (umpire_id) 
                DO UPDATE SET umpire_name = EXCLUDED.umpire_name;
            """), {"umpire_id": ump_id, "umpire_name": ump_name})

    # Step 2: Upsert game assignments securely using the newly registered foreign keys
    print(f"Linking assignments for {len(game_assignments)} matches...")
    with engine.begin() as conn:
        for assign in game_assignments:
            conn.execute(text("""
                INSERT INTO game_umpires (game_pk, hp_umpire_id, ump_1b_id, ump_2b_id, ump_3b_id)
                VALUES (:game_pk, :hp_umpire_id, :ump_1b_id, :ump_2b_id, :ump_3b_id)
                ON CONFLICT (game_pk) 
                DO UPDATE SET 
                    hp_umpire_id = EXCLUDED.hp_umpire_id,
                    ump_1b_id = EXCLUDED.ump_1b_id,
                    ump_2b_id = EXCLUDED.ump_2b_id,
                    ump_3b_id = EXCLUDED.ump_3b_id;
            """), assign)
            
    print("Relational umpire system successfully synchronized!")
