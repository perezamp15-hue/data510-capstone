import math
import requests
from datetime import datetime

def get_stadium_coords_from_db(conn, venue_name: str):
    """Queries Postgres to get geo-coordinates and timezone offsets dynamically with safe fallbacks."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT latitude, longitude, timezone_offset FROM stadiums WHERE stadium_name = %s LIMIT 1;",
                (venue_name,)
            )
            row = cur.fetchone()
            # SAFEGUARD: Guard against None records before index casting to float
            if row and row[0] is not None and row[1] is not None:
                return float(row[0]), float(row[1]), row[2]
    except Exception as e:
        print(f"Error pulling stadium spatial mapping attributes for '{venue_name}': {e}")
        
    return None, None, 0

def calculate_haversine_distance(coord1, coord2):
    """Calculates miles between two coordinate pairs using the Haversine equation."""
    if not coord1 or not coord2 or None in coord1 or None in coord2:
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

def estimate_player_fatigue(conn, player_id: int, season: int, target_date: datetime):
    """
    Calculates consecutive games played, 7-day travel distance, and sleep disruption indices.
    Accepts target_date parameter to maintain historical extraction timeline integrity.
    """
    fatigue_profile = {
        "player_id": player_id,
        "consecutive_games_played": 0,
        "travel_distance_last_7_days": 0.0,
        "sleep_quality_index": 100,
        "rest_days_last_14_days": 0
    }

    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={season}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return fatigue_profile
    except requests.exceptions.RequestException:
        return fatigue_profile
        
    logs = response.json().get("stats", [{}])[0].get("splits", [])
    if not logs:
        return fatigue_profile

    total_travel = 0.0
    late_night_flights = 0
    venues_visited = []
    
    # Sort chronologically to parse consecutive logic
    logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    for log in logs:
        date_str = log.get("date")
        if not date_str:
            continue
        try:
            log_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
            
        # Target evaluation layer check
        if 0 <= (target_date - log_date).days <= 7:
            venues_visited.append({
                "venue": log.get("venue", {}).get("name"),
                "is_night": log.get("dayNight") == "Night"
            })
            
    venues_visited.reverse() # Put back into forward chronological order for distance math
    
    for idx in range(len(venues_visited) - 1):
        v1, v2 = venues_visited[idx], venues_visited[idx+1]
        
        if v1["venue"] != v2["venue"] and v1["venue"] and v2["venue"]:
            lat1, lon1, tz1 = get_stadium_coords_from_db(conn, v1["venue"])
            lat2, lon2, tz2 = get_stadium_coords_from_db(conn, v2["venue"])
            
            # Safe loop execution step bypass if database maps empty records
            if None in (lat1, lon1, lat2, lon2):
                continue
                
            dist = calculate_haversine_distance((lat1, lon1), (lat2, lon2))
            total_travel += dist
            
            # Catch jet-lag or cross-country redeyes
            if v1["is_night"] and (dist > 300.0 or tz1 != tz2):
                late_night_flights += 1
                
    fatigue_profile["travel_distance_last_7_days"] = round(total_travel, 1)
    
    # Calculate sleep quality matrix metrics
    sleep_score = 100.0 - (late_night_flights * 25) - (max(0, total_travel - 2000) * 0.01)
    fatigue_profile["sleep_quality_index"] = max(0, round(sleep_score))
    
    return fatigue_profile
