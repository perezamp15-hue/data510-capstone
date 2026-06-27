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
                pitchers = box_data.get('teams', {}).get(side, {}).get('pitchers', [])
                if len(pitchers) <= 1: continue
                for p_id in pitchers[1:]:
                    if int(p_id) not in valid_players: continue
                    p_stats = box_data.get('teams', {}).get(side, {}).get('players', {}).get(f"ID{p_id}", {}).get('stats', {}).get('pitching', {})
                    ip_str, pitches, bf = p_stats.get('inningsPitched', '0.0'), p_stats.get('pitchesThrown', 0), p_stats.get('battersFaced', 0)
                    if pitches == 0: continue
                    bp_dict = {"game_pk": pk, "pitcher_id": int(p_id), "innings_pitched": float(ip_str), "pitches_thrown": int(pitches), "batters_faced": int(bf)}
                    with engine.begin() as conn:
                        conn.execute(text("""
                            INSERT INTO bullpen_appearances (game_pk, pitcher_id, innings_pitched, pitches_thrown, batters_faced)
                            VALUES (:game_pk, :pitcher_id, :innings_pitched, :pitches_thrown, :batters_faced)
                            ON CONFLICT (game_pk, pitcher_id) DO UPDATE SET innings_pitched = EXCLUDED.innings_pitched, pitches_thrown = EXCLUDED.pitches_thrown, batters_faced = EXCLUDED.batters_faced;
                        """), bp_dict)
        except Exception: continue

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
