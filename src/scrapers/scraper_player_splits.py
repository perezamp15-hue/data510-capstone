import requests

def fetch_player_splits(player_id: int, season: int, group: str = "hitting"):
    """
    Fetches extensive situational splits for a player.
    Dynamically maps hitting vs pitching schema keys to maintain database format integrity.
    """
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statSplits&group={group}&season={season}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    splits_extracted = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return splits_extracted
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching splits for player {player_id}: {e}")
        return splits_extracted
        
    data = response.json()
    
    def safe_float(val):
        try:
            return float(val) if val not in (None, "", "null", ".---") else 0.0
        except ValueError:
            return 0.0

    for stat_type in data.get("stats", []):
        for split in stat_type.get("splits", []):
            split_info = split.get("split", {})
            stats = split.get("stat", {})
            
            # FIXED: Dynamic dictionary mapping layers to catch split-group property variances
            if group == "pitching":
                pa_count = stats.get("battersFaced")
                k_count = stats.get("strikeOuts")
            else:
                pa_count = stats.get("plateAppearances")
                k_count = stats.get("strikeouts")
                
            split_record = {
                "player_id": int(player_id),
                "season": int(season),
                "split_group": group,
                "split_name": split_info.get("name"),  # e.g., "vs Left", "Home"
                "split_code": split_info.get("code"),
                "games_played": int(stats.get("gamesPlayed", 0) or 0),
                "plate_appearances": int(pa_count or 0),
                "avg": safe_float(stats.get("avg")),
                "obp": safe_float(stats.get("obp")),
                "slg": safe_float(stats.get("slg")),
                "ops": safe_float(stats.get("ops")),
                "home_runs": int(stats.get("homeRuns", 0) or 0),
                "strikeouts": int(k_count or 0),
                "walks": int(stats.get("baseOnBalls", 0) or 0)
            }
            splits_extracted.append(split_record)
            
    return splits_extracted
