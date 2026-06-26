import requests

def fetch_pitcher_platoon_splits(player_id: int, season: int):
    """
    Scrapes a pitcher's statistical splits against left-handed 
    and right-handed batters for a specific season.
    """
    # StatsAPI platoon split configuration endpoint
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        f"?stats=statSplits&group=pitching&sitCodes=vl,vr&season={season}"
    )
    
    response = requests.get(url)
    
    # Pre-structure dictionary for tracking target platoon splits
    platoon_payload = {
        "player_id": player_id,
        "season": season,
        "vs_lefties":  {"avg_allowed": .000, "hr_allowed": 0, "ops_allowed": .000},
        "vs_righties": {"avg_allowed": .000, "hr_allowed": 0, "ops_allowed": .000}
    }
    
    if response.status_code != 200:
        print(f"Error pulling platoon splits for pitcher {player_id}")
        return platoon_payload
        
    data = response.json()
    stats_list = data.get("stats", [])
    if not stats_list:
        return platoon_payload
        
    splits = stats_list[0].get("splits", [])
    
    for split in splits:
        code = split.get("split", {}).get("code")  # 'vl' = vs Left, 'vr' = vs Right
        stat = split.get("stat", {})
        
        metrics = {
            "avg_allowed": float(stat.get("avg", ".000")),
            "hr_allowed": int(stat.get("homeRuns", 0)),
            "ops_allowed": float(stat.get("ops", ".000"))
        }
        
        # Map back to our cleaner simulator dictionary format
        if code == "vl":    # vs Left-handed batters
            platoon_payload["vs_lefties"] = metrics
        elif code == "vr":  # vs Right-handed batters
            platoon_payload["vs_righties"] = metrics

    return platoon_payload
