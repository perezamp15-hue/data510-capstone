import requests

def fetch_pitcher_platoon_splits(player_id: int, season: int):
    """
    Scrapes a pitcher's statistical splits against left-handed 
    and right-handed batters for a specific season.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        f"?stats=statSplits&group=pitching&sitCodes=vl,vr&season={season}"
    )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    platoon_payload = {
        "player_id": player_id,
        "season": season,
        "vs_lefties":  {"avg_allowed": 0.0, "hr_allowed": 0, "ops_allowed": 0.0},
        "vs_righties": {"avg_allowed": 0.0, "hr_allowed": 0, "ops_allowed": 0.0}
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout pulling platoon splits for pitcher {player_id}: {e}")
        return platoon_payload
        
    if response.status_code != 200:
        return platoon_payload
        
    data = response.json()
    stats_list = data.get("stats", [])
    if not stats_list:
        return platoon_payload
        
    splits = stats_list[0].get("splits", [])
    
    def safe_float(val):
        try:
            return float(val) if val not in (None, "", "null", ".---") else 0.0
        except ValueError:
            return 0.0

    for split in splits:
        code = split.get("split", {}).get("code")  # 'vl' = vs Left, 'vr' = vs Right
        stat = split.get("stat", {})
        
        metrics = {
            "avg_allowed": safe_float(stat.get("avg")),
            "hr_allowed": int(stat.get("homeRuns", 0)),
            "ops_allowed": safe_float(stat.get("ops"))
        }
        
        if code == "vl":    
            platoon_payload["vs_lefties"] = metrics
        elif code == "vr":  
            platoon_payload["vs_righties"] = metrics

    return platoon_payload
