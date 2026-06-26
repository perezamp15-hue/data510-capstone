import requests

def fetch_meteorological_weather(lat: float, lon: float, date_str: str, hour_24: int):
    """
    Fetches hyper-precise physical weather tracking parameters from historical data.
    """
    if not lat or not lon:
        return {}

    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}"
        f"&hourly=temperature_2m,relative_humidity_2m,dew_point_2m,surface_pressure,cloud_cover,precipitation_probability"
    )
    response = requests.get(url)
    
    metrics = {
        "temperature": None, "humidity": None, "wind_speed": None, 
        "air_pressure": None, "cloud_cover": None, "rain_percentage": None, "dew_point": None
    }
    
    if response.status_code == 200:
        data = response.json()
        hourly_data = data.get("hourly", {})
        
        # Pull values corresponding to the hour of the game
        # (e.g., a 7:00 PM game would extract index 19 from the 24-hour array)
        idx = max(0, min(hour_24, 23)) 
        
        metrics["temperature"] = hourly_data.get("temperature_2m", [None])[idx]
        metrics["humidity"] = hourly_data.get("relative_humidity_2m", [None])[idx]
        metrics["dew_point"] = hourly_data.get("dew_point_2m", [None])[idx]
        metrics["air_pressure"] = hourly_data.get("surface_pressure", [None])[idx]
        metrics["cloud_cover"] = hourly_data.get("cloud_cover", [None])[idx]
        metrics["rain_percentage"] = hourly_data.get("precipitation_probability", [None])[idx]
        
    return metrics
