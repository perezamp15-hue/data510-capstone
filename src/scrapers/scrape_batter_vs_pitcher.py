import requests

def fetch_batter_vs_pitcher(batter_id: int, pitcher_id: int):
    """
    Scrapes the exact historical career matchup data between a specific 
    batter and pitcher using their unique MLB ID numbers.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
        f"?stats=vsPlayer&group=hitting&opposingPlayerId={pitcher_id}"
    )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    bvp_payload = {
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "plate_appearances": 0,
        "avg": 0.000,
        "ops": 0.000,
        "strikeouts": 0,
        "walks": 0,
        "home_runs": 0,
        "avg_exit_velocity": None
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching matchup for Hitter:{batter_id} vs Pitcher:{pitcher_id}")
        return bvp_payload
        
    if response.status_code != 200:
        return bvp_payload
        
    data = response.json()
    stats_list = data.get("stats", [])
    if not stats_list:
        return bvp_payload
        
    splits = stats_list[0].get("splits", [])
    if not splits:
        return bvp_payload
        
    stat = splits[0].get("stat", {})
    
    # Safe float conversion helper to prevent crash on unexpected empty string representations
    def safe_float(val):
        try:
            return float(val) if val not in (None, "", "null", ".---") else 0.0
        except ValueError:
            return 0.0

    bvp_payload.update({
        "plate_appearances": stat.get("plateAppearances", 0),
        "avg": safe_float(stat.get("avg")),
        "ops": safe_float(stat.get("ops")),
        "strikeouts": stat.get("strikeOuts", 0),
        "walks": stat.get("baseOnBalls", 0),
        "home_runs": stat.get("homeRuns", 0)
    })
    
    # Advanced tracking values inside matchup metrics
    hit_data = stat.get("hitData", {})
    bvp_payload["avg_exit_velocity"] = hit_data.get("launchSpeed") if isinstance(hit_data, dict) else None
    
    return bvp_payload
