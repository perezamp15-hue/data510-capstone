import requests
from datetime import date

def fetch_environmental_weather(conn, game_pk: int):
    """
    Fetches game weather conditions with automated indoor stadium suppression rules.
    Safely reads stadium physical roof configurations directly from relational database tables.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    weather_payload = {
        "game_pk": game_pk,
        "temperature": None,
        "condition_description": "Unknown",
        "wind_speed_mph": 0.0,
        "wind_direction": "None",
        "relative_humidity_pct": 50.0, # Standard air density fallback
        "barometric_pressure_inHg": 29.92
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching weather data for game {game_pk}: {e}")
        return weather_payload
        
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
        
    # Process basic raw temperature readings safely
    try:
        if "degrees" in weather_str:
            temp_part = weather_str.split("degrees")[0].strip()
            # Handle possible trailing commas or spaces
            if "," in temp_part:
                temp_part = temp_part.split(",")[-1].strip()
            weather_payload["temperature"] = float(temp_part)
    except (ValueError, IndexError):
        pass
        
    # --- Dynamic Database Structural Check ---
    roof_type = "open"
    try:
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
            if row and row[0]:
                roof_type = str(row[0]).lower()
    except Exception as e:
        print(f"Query alert verifying stadium roof type structural properties for game {game_pk}: {e}")

    # Strict physical override rule: If database flags a dome or raw string declares closed status
    if "dome" in roof_type or "closed" in weather_str.lower():
        weather_payload["condition_description"] = "Controlled Environment"
        weather_payload["wind_speed_mph"] = 0.0
        weather_payload["wind_direction"] = "Indoor"
    else:
        weather_payload["condition_description"] = weather_str[:255] # Ensure safe length bound for strings
        
        # Parse wind information if available
        try:
            if "Wind" in weather_str:
                wind_part = weather_str.split("Wind")[-1].strip()
                # Parse wind speed out of string tokens (e.g., "8 mph, Out To LF")
                speed_token = wind_part.split("mph")[0].strip()
                weather_payload["wind_speed_mph"] = float(speed_token)
                
                if "," in wind_part:
                    weather_payload["wind_direction"] = wind_part.split(",")[-1].strip()
        except (ValueError, IndexError):
            pass
        
    return weather_payload
