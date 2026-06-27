import requests

def fetch_boxscore_data(conn=None, game_pk: int = None):
    """
    Fetches post-game details and roof/wind statuses from the boxscore endpoint.
    Accepts conn context optionally to match unified transaction architectures.
    """
    if game_pk is None:
        # Fallback if positional parameter shifts
        return {
            "attendance": None, "umpire_crew": [], "actual_start_time": None,
            "roof_status": "Open", "mlb_wind_string": None
        }

    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    boxscore_data = {
        "attendance": None,
        "umpire_crew": [],
        "actual_start_time": None,
        "roof_status": "Open",
        "mlb_wind_string": None
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout pulling boxscore for game {game_pk}: {e}")
        return boxscore_data
        
    if response.status_code != 200:
        return boxscore_data
        
    data = response.json()
    game_info_list = data.get("info", [])
    
    # 1. Parse official text strings with case-insensitive structural normalization
    for item in game_info_list:
        label = item.get("label", "").strip()
        value = item.get("value", "").strip()
        
        if label == "Weather":
            if any(status in value for status in ["Roof Closed", "Closed", "roof closed"]):
                boxscore_data["roof_status"] = "Closed"
            elif "Dome" in value or "dome" in value:
                boxscore_data["roof_status"] = "Dome"
        elif label == "Wind":
            boxscore_data["mlb_wind_string"] = value
        elif label in ("Att", "Attendance"):
            try:
                boxscore_data["attendance"] = int(value.replace(",", ""))
            except ValueError:
                pass

    # 2. Extract Umpires
    for official in data.get("officials", []):
        off_type = official.get("officialType", {}).get("description", "")
        if "Umpire" in off_type:
            name = official.get("official", {}).get("fullName")
            if name:
                boxscore_data["umpire_crew"].append(name)
            
    return boxscore_data
