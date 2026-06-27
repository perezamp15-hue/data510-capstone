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
                batters = box_data.get('teams', {}).get(side, {}).get('batters', [])
                slot = 1
                for b_id in batters:
                    if int(b_id) not in valid_players: continue
                    p_info = box_data.get('teams', {}).get(side, {}).get('players', {}).get(f"ID{b_id}", {})
                    lineup_dict = {
                        "game_pk": pk, "team_id": team_id, "batting_order_slot": slot, "player_id": int(b_id),
                        "field_position": p_info.get('position', {}).get('code', 'DH'), "batting_side": p_info.get('person', {}).get('batSide', {}).get('code', 'R')
                    }
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO starting_lineups (game_pk, team_id, batting_order_slot, player_id, field_position, batting_side)
                            VALUES (:game_pk, :team_id, :batting_order_slot, :player_id, :field_position, :batting_side)
                            ON CONFLICT (game_pk, team_id, batting_order_slot) DO UPDATE SET player_id = EXCLUDED.player_id, field_position = EXCLUDED.field_position;
                        """), lineup_dict)
                    slot += 1
                    if slot > 9: break
        except Exception: continue

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
