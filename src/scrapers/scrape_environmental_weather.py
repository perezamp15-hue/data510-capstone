from datetime import date
import requests

def fetch_environmental_weather(conn, game_pk: int):
    """Fetches real game weather conditions with automated indoor stadium suppression rules."""
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    response = requests.get(url)
    
    weather_payload = {
        "game_pk": game_pk,
        "temperature": None,
        "condition_description": "Unknown",
        "wind_speed_mph": 0.0,
        "wind_direction": "None",
        "relative_humidity_pct": 50, # Standard air density fallback
        "barometric_pressure_inHg": 29.92
    }
    
    if response.status_code != 200:
        return weather_payload
        
    info = response.json().get("info", [])
    weather_str = ""
    for item in info:
        if item.get("label") == "Weather":
            weather_str = item.get("value", "")
            break
            
    if not weather_str:
        return weather_payload
        
    # Standard string parsing block...
    # Parse e.g., "72 degrees, roof closed, wind 0 mph" or "68 degrees, Clear, Wind 8 mph L to R"
    try:
        if "degrees" in weather_str:
            weather_payload["temperature"] = float(weather_str.split("degrees")[0].strip())
    except ValueError:
        pass
        
    # --- Dynamic DB Structural Check ---
    # Fetch the roof type of the stadium hosting this specific game_pk
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.roof_type FROM stadiums s 
            JOIN schedule sch ON sch.venue_id = s.venue_id 
            WHERE sch.game_pk = %s;
            """,
            (game_pk,)
        )
        row = cur.fetchone()
        roof_type = row[0].lower() if row and row[0] else "open"

    # Strict physical override: If the structural record flags a dome or explicitly notes closed status
    if "dome" in roof_type or "closed" in weather_str.lower():
        weather_payload["condition_description"] = "Controlled Environment"
        weather_payload["wind_speed_mph"] = 0.0
        weather_payload["wind_direction"] = "Indoor"
    else:
        weather_payload["condition_description"] = weather_str
        # Standard wind parsing logic goes here...
        
    return weather_payload
