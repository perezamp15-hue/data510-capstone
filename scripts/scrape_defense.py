import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

# Map text-based position codes to valid standard database integer IDs
POSITION_CODE_MAP = {
    "1": 1,  # Pitcher
    "2": 2,  # Catcher
    "3": 3,  # First Base
    "4": 4,  # Second Base
    "5": 5,  # Third Base
    "6": 6,  # Shortstop
    "7": 7,  # Left Field
    "8": 8,  # Center Field
    "9": 9,  # Right Field
}

def run(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        
    print(f"Running defensive alignments ingest for: {target_date}")
    engine = get_engine()
    
    try: 
        valid_games = pd.read_sql("SELECT game_pk FROM games WHERE game_date = %s", con=engine, params=(target_date,))['game_pk'].tolist()
    except Exception as e: 
        print(f"Failed to query games for defense update: {e}")
        return
        
    try:
        valid_players = pd.read_sql("SELECT player_id FROM players", con=engine)['player_id'].tolist()
    except Exception as e:
        print(f"Failed to query player list: {e}")
        return

    defense_count = 0
    for pk in valid_games:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            box_data = fetch_api_json(url)
            for side in ['home', 'away']:
                team_node = box_data.get('teams', {}).get(side, {})
                team_id = team_node.get('team', {}).get('id')
                if not team_id:
                    continue
                    
                players_node = team_node.get('players', {})
                for p_key, p_val in players_node.items():
                    p_id = p_val.get('person', {}).get('id')
                    if not p_id or int(p_id) not in valid_players: 
                        continue
                        
                    status = p_val.get('position', {})
                    pos_code = status.get('code')
                    
                    # Ignore Pitchers (1), DHs, or empty placeholders
                    if pos_code in ['1', 'DH', None] or pos_code not in POSITION_CODE_MAP: 
                        continue
                    
                    pos_id_int = POSITION_CODE_MAP[pos_code]
                    
                    def_dict = {
                        "game_pk": int(pk), 
                        "team_id": int(team_id), 
                        "player_id": int(p_id), 
                        "position_id": pos_id_int, 
                        "position_name": status.get('name', 'Fielder')
                    }
                    
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO defensive_alignments (game_pk, team_id, player_id, position_id, position_name)
                            VALUES (:game_pk, :team_id, :player_id, :position_id, :position_name)
                            ON CONFLICT (game_pk, team_id, position_id) DO UPDATE SET 
                                player_id = EXCLUDED.player_id,
                                position_name = EXCLUDED.position_name;
                        """), def_dict)
                    defense_count += 1
        except Exception as e: 
            print(f"Defensive alignment error for game {pk}: {e}")
            continue

    print(f"Defensive updates completed: Ingested {defense_count} positions.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
