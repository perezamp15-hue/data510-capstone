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
    for pk in valid_games:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/feed/live"
        try:
            data = fetch_api_json(url)
            info = data.get('gameData', {}).get('weather', {})
            temp_str = info.get('temp')
            if not temp_str: continue
            w_dict = {"game_pk": pk, "temperature_f": int(temp_str), "sky_condition": info.get('condition'), "wind_speed_mph": info.get('wind'), "wind_direction": info.get('direction')}
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO game_weather (game_pk, temperature_f, sky_condition, wind_speed_mph, wind_direction)
                    VALUES (:game_pk, :temperature_f, :sky_condition, :wind_speed_mph, :wind_direction)
                    ON CONFLICT (game_pk) DO UPDATE SET temperature_f = EXCLUDED.temperature_f, sky_condition = EXCLUDED.sky_condition;
                """), w_dict)
        except Exception: continue

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
