import math
from datetime import datetime
import requests

# Approximate stadium coordinates for calculating flight distances (Haversine formula)
STADIUM_COORDINATES = {
    "Fenway Park": (42.3467, -71.0972),
    "Yankee Stadium": (40.8296, -73.9262),
    "T-Mobile Park": (47.5914, -122.3325),
    # You will populate this dictionary completely or cross-reference your venue database
}

def calculate_haversine_distance(coord1, coord2):
    """Calculates the distance in miles between two coordinate tuples."""
    if not coord1 or not coord2:
        return 0.0
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    R = 3956  # Earth radius in miles
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(d_lat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def estimate_player_fatigue(player_id: int, season: int = 2026):
    """
    Analyzes historical gamelogs and travel patterns to estimate active 
    fatigue vectors, consecutive strain, travel wear, and sleep degradation.
    """
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={season}"
    response = requests.get(url)
    
    fatigue_profile = {
        "player_id": player_id,
        "consecutive_games_played": 0,
        "travel_distance_last_7_days": 0.0,
        "sleep_quality_index": 100,  # Scale out of 100
        "rest_days_last_14_days": 0
    }
    
    if response.status_code != 200:
        return fatigue_profile
        
    logs = response.json().get("stats", [{}])[0].get("splits", [])
    if not logs:
        return fatigue_profile
        
    # Sort chronologically (most recent first)
    logs.sort(key=lambda x: x.get("date"), reverse=True)
    
    # 1. Calculate Consecutive Games Played
    current_streak = 0
    # Fetch team schedule to check for actual team off-days vs player benchings
    # For this standalone script, we check if the player logged a game consecutively by date
    last_date_parsed = None
    
    for i, log in enumerate(logs):
        game_date = datetime.strptime(log.get("date"), "%Y-%m-%d")
        if i == 0:
            current_streak = 1
            last_date_parsed = game_date
            continue
            
        diff = (last_date_parsed - game_date).days
        if diff == 1:
            current_streak += 1
            last_date_parsed = game_date
        elif diff == 0:
            continue  # Doubleheader day
        else:
            break  # Streak broken
            
    fatigue_profile["consecutive_games_played"] = current_streak
    
    # 2. Travel Distance & Sleep Deprivation Approximation
    # Track the last 7 days of venue changes
    total_travel = 0.0
    late_night_flights = 0
    today = datetime.today()
    
    venues_visited = []
    for log in logs:
        log_date = datetime.strptime(log.get("date"), "%Y-%m-%d")
        if (today - log_date).days <= 7:
            venues_visited.append({
                "date": log_date,
                "venue": log.get("venue", {}).get("name"),
                "is_night": log.get("dayNight") == "Night"
            })
            
    # Reverse to process chronologically forward
    venues_visited.reverse()
    
    for idx in range(len(venues_visited) - 1):
        v1 = venues_visited[idx]
        v2 = venues_visited[idx+1]
        
        if v1["venue"] != v2["venue"]:
            coord1 = STADIUM_COORDINATES.get(v1["venue"])
            coord2 = STADIUM_COORDINATES.get(v2["venue"])
            dist = calculate_haversine_distance(coord1, coord2)
            total_travel += dist
            
            # Sleep Quality penalty: Did they fly to a new city immediately after a night game?
            if v1["is_night"] and dist > 300:
                late_night_flights += 1
                
    fatigue_profile["travel_distance_last_7_days"] = round(total_travel, 1)
    
    # Simple proxy formula for sleep: baseline 100 minus travel and back-to-back night/day strain
    sleep_score = 100 - (late_night_flights * 25)
    if current_streak > 10:
        sleep_score -= (current_streak - 10) * 2  # Accumulated wear penalty
    fatigue_profile["sleep_quality_index"] = max(40, sleep_score)
    
    # 3. Rest Days (Count days in past 2 weeks where player did not appear)
    active_days = set()
    for log in logs:
        log_date = datetime.strptime(log.get("date"), "%Y-%m-%d")
        if (today - log_date).days <= 14:
            active_days.add(log.get("date"))
            
    fatigue_profile["rest_days_last_14_days"] = 14 - len(active_days)
    
    return fatigue_profile
