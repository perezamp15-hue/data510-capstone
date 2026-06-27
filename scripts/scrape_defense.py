import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
    engine = get_engine()
    try: valid_games = pd.read_sql("SELECT game_pk FROM games WHERE game_date = %s", con=engine, params=(target_date,))['game_pk'].tolist()
    except Exception: return
    valid_players = pd.read_sql("SELECT player_id FROM players", con=engine)['player_id'].tolist()
    for pk in valid_games:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            box_data = fetch_api_json(url)
            for side in ['home', 'away']:
                team_id = int(box_data.get('teams', {}).get(side, {}).get('team', {}).get('id'))
                players_node = box_data.get('teams', {}).get(side, {}).get('players', {})
                for p_key, p_val in players_node.items():
                    p_id = p_val.get('person', {}).get('id')
                    if not p_id or int(p_id) not in valid_players: continue
                    status = p_val.get('position', {})
                    pos_id, pos_code = status.get('type'), status.get('code')
                    if pos_code == '1' or pos_code == 'DH' or not pos_id: continue
                    def_dict = {"game_pk": pk, "team_id": team_id, "player_id": int(p_id), "position_id": int(pos_id), "position_name": status.get('name', 'Fielder')}
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO defensive_alignments (game_pk, team_id, player_id, position_id, position_name)
                            VALUES (:game_pk, :team_id, :player_id, :position_id, :position_name)
                            ON CONFLICT (game_pk, team_id, position_id) DO UPDATE SET player_id = EXCLUDED.player_id;
                        """), def_dict)
        except Exception: continue

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
