import requests
from datetime import datetime

def fetch_game_information(target_date: str):
    """
    Fetches raw game essentials for a specific date (Format: 'YYYY-MM-DD').
    Includes linescore, officials, and venue hydration data.
    """
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={target_date}&hydrate=linescore,officials,venue"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching game schedule for {target_date}: {e}")
        return []
        
    if response.status_code != 200:
        print(f"Failed to fetch games for {target_date} (Status: {response.status_code})")
        return []
        
    data = response.json()
    games_parsed = []
    
    dates_list = data.get("dates", [])
    if not dates_list:
        return []
        
    for game in dates_list[0].get("games", []):
        game_pk = game.get("gamePk")
        if not game_pk:
            continue
            
        # Parse Time strings safely into database-ready ISO strings
        game_date_utc = game.get("gameDate") 
        try:
            dt_obj = datetime.strptime(game_date_utc, "%Y-%m-%dT%H:%M:%SZ")
            formatted_date = dt_obj.strftime("%Y-%m-%d")
            formatted_time = dt_obj.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            formatted_date = target_date
            formatted_time = "00:00:00"
        
        # Umpires extraction (populates post-game)
        umpires = []
        officials = game.get("officials", [])
        for official in officials:
            if "Umpire" in official.get("officialType", {}).get("description", ""):
                name = official.get("official", {}).get("fullName")
                if name:
                    umpires.append(name)

        game_info = {
            "game_pk": int(game_pk),
            "game_date": formatted_date,
            "scheduled_time": formatted_time,
            "actual_start_time": game.get("linescore", {}).get("resumeTime"),
            "stadium": game.get("venue", {}).get("name"),
            "venue_id": game.get("venue", {}).get("id"),
            "home_team": game.get("teams", {}).get("home", {}).get("team", {}).get("name"),
            "home_team_id": game.get("teams", {}).get("home", {}).get("team", {}).get("id"),
            "away_team": game.get("teams", {}).get("away", {}).get("team", {}).get("name"),
            "away_team_id": game.get("teams", {}).get("away", {}).get("team", {}).get("id"),
            "attendance": game.get("attendance"), 
            "umpire_crew": umpires,
            "day_night": game.get("dayNight"),
            "series_game_number": game.get("seriesGameNumber")
        }
        games_parsed.append(game_info)
        
    return games_parsed
