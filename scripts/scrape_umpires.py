import pandas as pd
from sqlalchemy.exc import IntegrityError
from db_client import get_engine, fetch_api_json

def extract_umpires_for_game(game_pk):
    """
    Queries the live game boxscore to pull the assigned official crew.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
    try:
        data = fetch_api_json(url)
        live_data = data.get('liveData', {})
        boxscore = live_data.get('boxscore', {})
        officials = boxscore.get('officials', [])
        
        ump_record = {
            "game_pk": game_pk,
            "hp_umpire": None,
            "ump_1b": None,
            "ump_2b": None,
            "ump_3b": None
        }
        
        for official in officials:
            position = official.get('officialType')
            name = official.get('official', {}).get('fullName')
            if position == 'Home Plate': ump_record['hp_umpire'] = name
            elif position == 'First Base': ump_record['ump_1b'] = name
            elif position == 'Second Base': ump_record['ump_2b'] = name
            elif position == 'Third Base': ump_record['ump_3b'] = name
            
        return ump_record
    except Exception as e:
        print(f"No umpire context loaded for {game_pk}: {e}")
        return None

def run(target_date):
    print(f"Gathering umpire official profiles for {target_date}...")
    engine = get_engine()
    
    try:
        games_df = pd.read_sql(f"SELECT game_pk FROM games WHERE game_date = '{target_date}'", con=engine)
        game_pks = games_df['game_pk'].tolist()
    except Exception as e:
        print(f"Could not read games list from database: {e}")
        return

    umpire_records = []
    for pk in game_pks:
        record = extract_umpires_for_game(pk)
        if record:
            umpire_records.append(record)
            
    if not umpire_records:
        print(f"No umpire profiles compiled for {target_date}.")
        return

    umpires_df = pd.DataFrame(umpire_records)
    
    # Database Insertion with Relational Integrity Filtering
    try:
        umpires_df.to_sql("game_umpires", con=engine, if_exists="append", index=False)
        print(f"Umpire assignments saved successfully for {len(umpires_df)} matchups.")
    except IntegrityError:
        print("Foreign key constraint flagged. Aligning umpire rows against saved parent IDs...")
        
        # Verify valid parent records in the data layer
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        
        # Filter down rows to guaranteed parent matches
        safe_df = umpires_df[umpires_df['game_pk'].isin(valid_games)]
        
        if not safe_df.empty:
            safe_df.to_sql("game_umpires", con=engine, if_exists="append", index=False)
            print(f"Successfully processed {len(safe_df)} clean umpire lists.")
        else:
            print("Umpire synchronization skipped: Matching parent game missing from database.")
