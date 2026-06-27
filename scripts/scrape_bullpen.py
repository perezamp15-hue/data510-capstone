import pandas as pd
from sqlalchemy.exc import IntegrityError
from db_client import get_engine, fetch_api_json

def get_bullpen_data(game_pk):
    """
    Fetches raw bullpen performance metrics from the live API feed.
    Returns a list of dicts or an empty list if data is missing.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
    try:
        data = fetch_api_json(url)
        # Parse out your team's bullpen stats from the JSON payload here
        # (This structure assumes you extract relevant fields into a clean dictionary)
        records = []
        
        # Example processing logic placeholder:
        live_data = data.get('liveData', {})
        boxscore = live_data.get('boxscore', {})
        teams = boxscore.get('teams', {})
        
        for team_type in ['home', 'away']:
            team_stats = teams.get(team_type, {})
            pitchers = team_stats.get('pitchers', [])
            # ... Your custom extraction filtering out starting pitchers ...
            
        return records
    except Exception as e:
        print(f"Skipping bullpen check for {game_pk}: {e}")
        return []

def run(target_date):
    print(f"Extracting bullpen appearances for games on {target_date}...")
    engine = get_engine()
    
    # 1. Pull the list of scheduled game IDs from the database for this date
    try:
        games_df = pd.read_sql(f"SELECT game_pk FROM games WHERE game_date = '{target_date}'", con=engine)
        game_pks = games_df['game_pk'].tolist()
    except Exception as e:
        print(f"Could not read games list from database: {e}")
        return

    all_bullpen_records = []
    for pk in game_pks:
        records = get_bullpen_data(pk)
        if records:
            all_bullpen_records.extend(records)
            
    if not all_bullpen_records:
        print(f"No bullpen statistics extracted for {target_date}.")
        return

    bullpen_df = pd.DataFrame(all_bullpen_records)
    
    # 2. Database Insertion with Relational Integrity Filtering
    try:
        bullpen_df.to_sql("bullpen_appearances", con=engine, if_exists="append", index=False)
        print(f"Successfully processed {len(bullpen_df)} bullpen entries.")
    except IntegrityError:
        print("Foreign key violation caught. Filtering bullpen entries against active database records...")
        
        # Retrieve the definitive list of game IDs currently saved in your database instance
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        
        # Keep only records where the parent game exists
        safe_df = bullpen_df[bullpen_df['game_pk'].isin(valid_games)]
        
        if not safe_df.empty:
            safe_df.to_sql("bullpen_appearances", con=engine, if_exists="append", index=False)
            print(f"Successfully synchronized {len(safe_df)} safe bullpen entries.")
        else:
            print("Bullpen synchronization skipped: No parent game entries found in DB.")
