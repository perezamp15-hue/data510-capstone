import pandas as pd
from sqlalchemy.exc import IntegrityError
from db_client import get_engine, fetch_api_json

def save_lineups_to_db(lineups_df):
    if lineups_df is None or lineups_df.empty:
        return
        
    engine = get_engine()
    
    try:
        # Quick path attempt
        lineups_df.to_sql("starting_lineups", con=engine, if_exists="append", index=False)
        print("Lineup batch updated successfully.")
    except IntegrityError:
        print("Foreign key mismatch detected. Filtering out missing parent game records...")
        
        # Pull only valid game primary keys currently tracked in your base tables
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        
        # Filter dataframe dynamically
        safe_df = lineups_df[lineups_df['game_pk'].isin(valid_games)]
        
        if not safe_df.empty:
            safe_df.to_sql("starting_lineups", con=engine, if_exists="append", index=False)
            print(f"Successfully tracked {len(safe_df)} clean situational entries.")
        else:
            print("Skipping insert: No parent match inside the 'games' table exists yet.")

def run(date_str=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    sched_data = fetch_api_json(sched_url)
    
    lineups = []
    for date_obj in sched_data.get("dates", []):
        for g in date_obj.get("games", []):
            game_pk = g.get("gamePk")
            box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
            try:
                box_data = fetch_api_json(box_url)
                for team_side in ['home', 'away']:
                    team_name = box_data['teams'][team_side]['team']['name']
                    batters_order = box_data['teams'][team_side].get('battingOrder', [])
                    
                    for index, player_id in enumerate(batters_order):
                        p_key = f"ID{player_id}"
                        player_info = box_data['teams'][team_side]['players'].get(p_key, {})
                        lineups.append({
                            "game_pk": game_pk,
                            "team": team_name,
                            "batting_order": index + 1,
                            "player_id": player_id,
                            "position": player_info.get('position', {}).get('abbreviation'),
                            "handedness": player_info.get('person', {}).get('batSide', {}).get('code')
                        })
            except Exception as e:
                print(f"Could not load lineup data for game {game_pk}: {e}")

    if lineups:
        pd.DataFrame(lineups).to_sql('starting_lineups', get_engine(), if_exists='append', index=False)
