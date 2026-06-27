import sys
from datetime import datetime, timedelta
import pandas as pd
from scripts.db_client import get_engine, fetch_api_json

def run(date_str=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    sched_data = fetch_api_json(sched_url)
    
    weather_records = []
    for date_obj in sched_data.get("dates", []):
        for g in date_obj.get("games", []):
            game_pk = g.get("gamePk")
            live_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
            try:
                live_data = fetch_api_json(live_url)
                w = live_data.get("gameData", {}).get("weather", {})
                info = live_data.get("gameData", {}).get("gameInfo", {})
                
                weather_records.append({
                    "game_pk": game_pk,
                    "temperature": w.get("temp"),
                    "humidity": w.get("humidity"),
                    "wind_speed": w.get("wind"),
                    "condition": w.get("condition"),
                    "roof_open": True if info.get("roof") == "Open" else False,
                    "roof_closed": True if info.get("roof") == "Closed" else False
                })
            except Exception as e:
                print(f"No weather context loaded for {game_pk}: {e}")

    if weather_records:
        pd.DataFrame(weather_records).to_sql('game_weather', get_engine(), if_exists='append', index=False)
