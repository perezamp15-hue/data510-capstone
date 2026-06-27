import requests

def fetch_batter_statcast_metric(season: int):
    """
    Scrapes advanced Statcast bat tracking and expected metric leaderboards 
    directly from Baseball Savant components.
    """
    # Public underlying Savant target URLs for custom metrics mapping
    url = f"https://baseballsavant.mlb.com/leaderboard/custom?year={season}&type=batter&filter=&sort=1&sortDir=desc&csv=true"
    
    # Alternatively, use MLB's statAdvanced parameters
    mlb_advanced_url = f"https://statsapi.mlb.com/api/v1/stats?stats=statAdvanced&group=hitting&season={season}&sportId=1"
    response = requests.get(mlb_advanced_url)
    
    statcast_map = {}
    if response.status_code != 200:
        return statcast_map
        
    data = response.json()
    player_splits = data.get("stats", [{}])[0].get("splits", [])
    
    for item in player_splits:
        player_id = item.get("player", {}).get("id")
        stat = item.get("stat", {})
        
        statcast_map[player_id] = {
            "season": season,
            # --- Advanced Profiles ---
            "hard_hit_percentage": stat.get("hardHitPercentage"),
            "barrel_percentage": stat.get("barrelPercentage"),
            "chase_percentage": stat.get("zoneOutPercentages", {}).get("chase"), # O-Swing %
            "whiff_percentage": stat.get("whiffPercentage"),
            "contact_percentage": 100.0 - stat.get("whiffPercentage") if stat.get("whiffPercentage") else None
        }
        
    return statcast_map
