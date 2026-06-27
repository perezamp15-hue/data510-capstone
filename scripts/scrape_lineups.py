import pandas as pd
from sqlalchemy.exc import IntegrityError
from db_client import get_engine, fetch_api_json

def save_lineups_to_db(lineups_df):
    if lineups_df is None or lineups_df.empty:
        return
        
    engine = get_engine()
    
    try:
        # Standard insert
        lineups_df.to_sql("starting_lineups", con=engine, if_exists="append", index=False)
        print("Lineup batch updated successfully.")
    except IntegrityError:
        print("Foreign key mismatch. Filtering out missing game IDs...")
        
        # Pull valid primary keys safely without relying on a date column check
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        safe_df = lineups_df[lineups_df['game_pk'].isin(valid_games)]
        
        if not safe_df.empty:
            safe_df.to_sql("starting_lineups", con=engine, if_exists="append", index=False)
            print(f"Successfully tracked {len(safe_df)} clean lineup entries.")
        else:
            print("Skipping insert: No matching game records exist in the database.")

def run(target_date):
    print(f"Gathering starting lineups for {target_date}...")
    # Your extraction parser loops go here and hand off a DataFrame to save_lineups_to_db
    pass
