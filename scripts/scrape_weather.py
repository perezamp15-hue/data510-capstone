import sys
import re
import pandas as pd
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Running weather ingest for: {target_date}")
    engine = get_engine()
    
    try: 
        valid_games = pd.read_sql("SELECT game_pk FROM games WHERE game_date = %s", con=engine, params=(target_date,))['game_pk'].tolist()
    except Exception as e: 
        print(f"Failed to query games for weather update: {e}")
        return

    weather_count = 0
    for pk in valid_games:
        url = f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live"
        try:
            data = fetch_api_json(url)
            if not data:
                continue
                
            info = data.get('gameData', {}).get('weather', {})
            temp_str = info.get('temp')
            
            if not temp_str: 
                continue
                
            raw_wind = info.get('wind', '0')
            
            # 1. Parse the numerical wind speed safely
            wind_speed = "".join(filter(str.isdigit, str(raw_wind)))
            wind_speed_int = int(wind_speed) if wind_speed else 0

            # 2. Smart Direction Fallback Parsing
            # If 'direction' is empty, try splitting '12 mph, In From LF' to capture 'In From LF'
            direction_str = info.get('direction')
            if not direction_str or direction_str.strip() == "":
                if "," in str(raw_wind):
                    direction_str = str(raw_wind).split(",", 1)[1].strip()
                else:
                    direction_str = "None"

            w_dict = {
                "game_pk": int(pk), 
                "temperature_f": int(temp_str), 
                "sky_condition": info.get('condition'), 
                "wind_speed_mph": wind_speed_int, 
                "wind_direction": direction_str
            }
            
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO game_weather (game_pk, temperature_f, sky_condition, wind_speed_mph, wind_direction)
                    VALUES (:game_pk, :temperature_f, :sky_condition, :wind_speed_mph, :wind_direction)
                    ON CONFLICT (game_pk) DO UPDATE SET 
                        temperature_f = EXCLUDED.temperature_f, 
                        sky_condition = EXCLUDED.sky_condition,
                        wind_speed_mph = EXCLUDED.wind_speed_mph,
                        wind_direction = EXCLUDED.wind_direction;
                """), w_dict)
            weather_count += 1
        except Exception as e:
            continue

    print(f"Weather updates completed: Ingested {weather_count} records with directional fallbacks.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
