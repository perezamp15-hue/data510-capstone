import requests

def fetch_pitcher_season_stats(player_id: int, season: int):
    """
    Scrapes standard metrics, Statcast profiles, and basic arsenal distribution.
    """
    # 1. Base Seasonal Pitching Metrics
    base_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group=pitching&season={season}"
    # 2. Advanced Statcast/Quality Data Tracking
    adv_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statAdvanced&group=pitching&season={season}"
    
    payload = {
        "player_id": player_id, "season": season,
        "era": None, "whip": None, "k_pct": None, "bb_pct": None,
        "hr_9": None, "gb_pct": None, "fb_pct": None,
        "hard_hit_pct": None, "barrel_pct": None, "avg_exit_velo_allowed": None,
        "arsenal_distribution": {}
    }
    
    # Process Base Metrics
    res_base = requests.get(base_url)
    if res_base.status_code == 200:
        splits = res_base.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            payload["era"] = stat.get("era")
            payload["whip"] = stat.get("whip")
            payload["hr_9"] = stat.get("homeRunsPer9Innings")
            
            # Calculate K% and BB% based on Plate Appearances faced
            tbf = stat.get("battersFaced", 1)
            payload["k_pct"] = round((stat.get("strikeOuts", 0) / tbf) * 100, 1)
            payload["bb_pct"] = round((stat.get("baseOnBalls", 0) / tbf) * 100, 1)
            
    # Process Advanced Batted Ball Metrics
    res_adv = requests.get(adv_url)
    if res_adv.status_code == 200:
        splits = res_adv.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            payload["gb_pct"] = stat.get("groundBallPercentage")
            payload["fb_pct"] = stat.get("flyBallPercentage")
            payload["hard_hit_pct"] = stat.get("hardHitPercentage")
            payload["barrel_pct"] = stat.get("barrelPercentage")
            payload["avg_exit_velo_allowed"] = stat.get("averageExitVelocity")

    return payload
