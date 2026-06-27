import sys
from datetime import datetime, timedelta
import pandas as pd
from db_client import get_engine, fetch_api_json

def run(date_str=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    data = fetch_api_json(url)
    
    games_list = []
    for date_obj in data.get("dates", []):
        for g in date_obj.get("games", []):
            game_pk = g.get("gamePk")
            live_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
            try:
                live_data = fetch_api_json(live_url)
                game_data = live_data.get("gameData", {})
                live_linescore = live_data.get("liveData", {}).get("linescore", {})
                
                home_score = live_linescore.get("teams", {}).get("home", {}).get("runs", 0)
                away_score = live_linescore.get("teams", {}).get("away", {}).get("runs", 0)
                
                games_list.append({
                    "game_pk": game_pk,
                    "date": game_data.get("datetime", {}).get("originalDate"),
                    "season": game_data.get("game", {}).get("season"),
                    "venue": game_data.get("venue", {}).get("name"),
                    "home_team": game_data.get("teams", {}).get("home", {}).get("triCode"),
                    "away_team": game_data.get("teams", {}).get("away", {}).get("triCode"),
                    "start_time": game_data.get("datetime", {}).get("startTime"),
                    "attendance": game_data.get("gameInfo", {}).get("attendance"),
                    "duration": game_data.get("gameInfo", {}).get("durationMinutes"),
                    "home_score": home_score,
                    "away_score": away_score,
                    "winner": game_data.get("teams", {}).get("home", {}).get("triCode") if home_score > away_score else game_data.get("teams", {}).get("away", {}).get("triCode"),
                    "loser": game_data.get("teams", {}).get("away", {}).get("triCode") if home_score > away_score else game_data.get("teams", {}).get("home", {}).get("triCode")
                })
            except Exception as e:
                print(f"Skipping game {game_pk} due to error: {e}")

    if games_list:
        pd.DataFrame(games_list).to_sql('games', get_engine(), if_exists='append', index=False)
