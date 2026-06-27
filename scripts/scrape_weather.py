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
    
    print(f"Running weather ingest for: {target_date}")
    engine = get_engine()
    
    try: 
        valid_games = pd.read_sql("SELECT game_pk FROM games WHERE game_date = %s", con=engine, params=(target_date,))['game_pk'].tolist()
    except Exception as e: 
        print(f"Failed to query games for weather update: {e}")
        return

    weather_count = 0
    for pk in valid_games:
        # Crucial Fix: MLB live data feed requires the v1.1 endpoint path
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
            wind_speed = "".join(filter(str.isdigit, str(raw_wind)))
            wind_speed_int = int(wind_speed) if wind_speed else 0

            w_dict = {
                "game_pk": int(pk), 
                "temperature_f": int(temp_str), 
                "sky_condition": info.get('condition'), 
                "wind_speed_mph": wind_speed_int, 
                "wind_direction": info.get('direction')
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
            # Safely skip individual unmatched records without stopping the pipeline
            continue

    print(f"Weather updates completed: Ingested {weather_count} records.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
