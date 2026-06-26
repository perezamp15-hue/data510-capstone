import requests

def fetch_boxscore_data(game_pk: int):
    """
    Fetches post-game details and roof/wind statuses from the boxscore endpoint.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    response = requests.get(url)
    
    boxscore_data = {
        "attendance": None,
        "umpire_crew": [],
        "actual_start_time": None,
        "roof_status": "Open",
        "mlb_wind_string": None
    }
    
    if response.status_code != 200:
        return boxscore_data
        
    data = response.json()
    game_info_list = data.get("info", [])
    
    # 1. Parse official text strings
    for item in game_info_list:
        label = item.get("label")
        value = item.get("value")
        
        if label == "Weather":
            if any(status in value for status in ["Roof Closed", "Closed"]):
                boxscore_data["roof_status"] = "Closed"
            elif "Dome" in value:
                boxscore_data["roof_status"] = "Dome"
        elif label == "Wind":
            boxscore_data["mlb_wind_string"] = value
        elif label == "Att":
            try:
                boxscore_data["attendance"] = int(value.replace(",", ""))
            except ValueError:
                pass
        elif label == "T":
            # Game duration or start time string adjustments can go here
            pass

    # 2. Extract Umpires
    for official in data.get("officials", []):
        if official.get("officialType", {}).get("description") == "Umpire":
            boxscore_data["umpire_crew"].append(official.get("official", {}).get("fullName"))
            
    return boxscore_data
