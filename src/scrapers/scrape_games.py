import requests
from datetime import datetime, timedelta

def fetch_game_information(target_date: str):
    """
    Fetches raw game essentials for a specific date (Format: 'YYYY-MM-DD').
    Includes logic placeholder for post-game data (attendance, umpires).
    """
    # MLB StatsAPI schedule endpoint is completely free and public
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={target_date}&hydrate=linescore,officials,venue"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to fetch games for {target_date}")
        return []
        
    data = response.json()
    games_parsed = []
    
    # Safely navigate JSON structure
    dates_list = data.get("dates", [])
    if not dates_list:
        return []
        
    for game in dates_list[0].get("games", []):
        game_pk = game.get("gamePk")
        
        # Parse Time strings safely
        game_date_utc = game.get("gameDate") # ISO timestamp
        dt_obj = datetime.strptime(game_date_utc, "%Y-%m-%dT%H:%M:%SZ")
        
        # Umpires extraction (only populates post-game)
        umpires = []
        officials = game.get("officials", [])
        for official in officials:
            if official.get("officialType", {}).get("description") == "Umpire":
                umpires.append(official.get("official", {}).get("fullName"))

        # Base structure
        game_info = {
            "game_pk": game_pk,
            "game_date": dt_obj.date(),
            "scheduled_time": dt_obj.time(),
            "actual_start_time": game.get("linescore", {}).get("resumeTime"), # fallback to box score step if needed
            "stadium": game.get("venue", {}).get("name"),
            "home_team": game.get("teams", {}).get("home", {}).get("team", {}).get("name"),
            "away_team": game.get("teams", {}).get("away", {}).get("team", {}).get("name"),
            "attendance": game.get("attendance"), # Null if game hasn't happened yet
            "umpire_crew": umpires,
            "day_night": game.get("dayNight"),
            "series_game_number": game.get("seriesGameNumber")
        }
        games_parsed.append(game_info)
        
    return games_parsed
