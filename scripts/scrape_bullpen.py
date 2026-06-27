import pandas as pd
from sqlalchemy.exc import IntegrityError
from db_client import get_engine, fetch_api_json

def get_bullpen_data(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
    try:
        data = fetch_api_json(url)
        records = []
        live_data = data.get('liveData', {})
        boxscore = live_data.get('boxscore', {})
        teams = boxscore.get('teams', {})
        
        for team_type in ['home', 'away']:
            team_stats = teams.get(team_type, {})
            pitchers = team_stats.get('pitchers', [])
            # Custom parsing criteria logic goes here...
            
        return records
    except Exception as e:
        print(f"Skipping bullpen check for {game_pk}: {e}")
        return []

def run(target_date):
    print(f"Extracting bullpen appearances for games on {target_date}...")
    engine = get_engine()
    
    # Absolute protection query: grab existing game keys safely
    try:
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
    except Exception as e:
        print(f"Failed to read keys from database: {e}")
        return

    all_bullpen_records = []
    # Feed data loops
    for pk in valid_games:
        records = get_bullpen_data(pk)
        if records:
            all_bullpen_records.extend(records)
            
    if not all_bullpen_records:
        print(f"No bullpen statistics extracted for {target_date}.")
        return

    bullpen_df = pd.DataFrame(all_bullpen_records)
    
    try:
        bullpen_df.to_sql("bullpen_appearances", con=engine, if_exists="append", index=False)
        print(f"Successfully processed {len(bullpen_df)} bullpen entries.")
    except IntegrityError:
        # Fallback filter mapping verification
        safe_df = bullpen_df[bullpen_df['game_pk'].isin(valid_games)]
        if not safe_df.empty:
            safe_df.to_sql("bullpen_appearances", con=engine, if_exists="append", index=False)
            print(f"Successfully synchronized {len(safe_df)} safe bullpen entries.")
