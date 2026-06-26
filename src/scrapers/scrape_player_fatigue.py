import math
from datetime import datetime, date
import requests

def get_stadium_coords_from_db(conn, venue_name: str):
    """Queries Postgres to get geo-coordinates and timezone offsets dynamically."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT latitude, longitude, timezone_offset FROM stadiums WHERE stadium_name = %s LIMIT 1;",
            (venue_name,)
        )
        row = cur.fetchone()
        return (float(row[0]), float(row[1]), row[2]) if row and row[0] and row[1] else (None, None, 0)

def calculate_haversine_distance(coord1, coord2):
    """Calculates miles between two coordinate pairs."""
    if not coord1 or not coord2 or None in coord1 or None in coord2:
        return 0.0
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 3956  
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)

def estimate_player_fatigue(conn, player_id: int, season: int = None):
    """Analyzes recent travel wear, dynamically lookups coordinates from DB."""
   # Update function definition to accept target_date
    for log in logs:
        log_date = datetime.strptime(log.get("date"), "%Y-%m-%d")
        if 0 <= (target_date - log_date).days <= 7:
            # ...
        
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={season}"
    response = requests.get(url)
    
    fatigue_profile = {
        "player_id": player_id,
        "consecutive_games_played": 0,
        "travel_distance_last_7_days": 0.0,
        "sleep_quality_index": 100,
        "rest_days_last_14_days": 0
    }
    
    if response.status_code != 200:
        return fatigue_profile
        
    logs = response.json().get("stats", [{}])[0].get("splits", [])
    if not logs:
        return fatigue_profile
        
    logs.sort(key=lambda x: x.get("date"), reverse=True)
    
    # 1. Consecutive Games
    current_streak = 0
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
            continue
        else:
            break
    fatigue_profile["consecutive_games_played"] = current_streak
    
    # 2. Dynamic Travel Lookup & Sleep Index
    total_travel = 0.0
    late_night_flights = 0
    today = datetime.today()
    venues_visited = []
    
    for log in logs:
        log_date = datetime.strptime(log.get("date"), "%Y-%m-%d")
        if (today - log_date).days <= 7:
            venues_visited.append({
                "venue": log.get("venue", {}).get("name"),
                "is_night": log.get("dayNight") == "Night"
            })
    venues_visited.reverse()
    
    for idx in range(len(venues_visited) - 1):
        v1, v2 = venues_visited[idx], venues_visited[idx+1]
        if v1["venue"] != v2["venue"]:
            lat1, lon1, tz1 = get_stadium_coords_from_db(conn, v1["venue"])
            lat2, lon2, tz2 = get_stadium_coords_from_db(conn, v2["venue"])
            
            dist = calculate_haversine_distance((lat1, lon1), (lat2, lon2))
            total_travel += dist
            
            # Catch jet-lag or cross-country redeyes
            if v1["is_night"] and (dist > 300 or tz1 != tz2):
                late_night_flights += 1
                
    fatigue_profile["travel_distance_last_7_days"] = round(total_travel, 1)
    sleep_score = 100 - (late_night_flights * 25) - (max(0, current_streak - 10) * 2)
    fatigue_profile["sleep_quality_index"] = max(40, sleep_score)
    
    # 3. Rest Days
    active_days = {log.get("date") for log in logs if (today - datetime.strptime(log.get("date"), "%Y-%m-%d")).days <= 14}
    fatigue_profile["rest_days_last_14_days"] = 14 - len(active_days)
    
    return fatigue_profile
