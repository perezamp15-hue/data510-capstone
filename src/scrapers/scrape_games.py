import requests
from datetime import datetime

def fetch_daily_games(game_date: str):
    """
    Fetches game-level metadata, weather, and venue details for a specific date (YYYY-MM-DD).
    """
    # MLB StatsAPI schedule endpoint with extra detail flags
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={game_date}&hydrate=weather,venue,linescore,decisions,umpire"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Error fetching schedule for {game_date}")
        return []
        
    data = response.json()
    games_extracted = []
    
    for date_obj in data.get("dates", []):
        for game in date_obj.get("games", []):
            venue = game.get("venue", {})
            weather = game.get("weather", {})
            
            game_info = {
                "game_pk": game.get("gamePk"),
                "date": game_date,
                "game_time": game.get("gameDate"),
                "stadium_name": venue.get("name"),
                "stadium_id": venue.get("id"),
                "home_team_id": game.get("teams", {}).get("home", {}).get("team", {}).get("id"),
                "away_team_id": game.get("teams", {}).get("away", {}).get("team", {}).get("id"),
                "temperature": weather.get("temp"),
                "condition": weather.get("condition"),
                "wind": weather.get("wind"),  # e.g., "11 mph, In From CF"
                "roof_type": game.get("roofType")
            }
            games_extracted.append(game_info)
            
    return games_extracted
