import requests

# Cache storage to prevent hitting the API repeatedly for every single player inside your pipeline loop
_STATCAST_CACHE = {}

def fetch_batter_statcast(player_id: int, season: int):
    """
    Scrapes advanced Statcast leaderboards for the entire league and filters 
    metrics down to the targeted player_id.
    """
    global _STATCAST_CACHE
    
    # If the cache is empty for this season, populate it with a single efficient API call
    if not _STATCAST_CACHE or _STATCAST_CACHE.get("season_key") != season:
        mlb_advanced_url = f"https://statsapi.mlb.com/api/v1/stats?stats=statAdvanced&group=hitting&season={season}&sportId=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            response = requests.get(mlb_advanced_url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                player_splits = data.get("stats", [{}])[0].get("splits", [])
                
                # Reset cache and track target season
                _STATCAST_CACHE = {"season_key": season}
                
                for item in player_splits:
                    pid = item.get("player", {}).get("id")
                    stat = item.get("stat", {})
                    
                    # Safely dig into nested metrics structure
                    zone_outs = stat.get("zoneOutPercentages", {})
                    chase = zone_outs.get("chase") if isinstance(zone_outs, dict) else None
                    whiff = stat.get("whiffPercentage")
                    
                    _STATCAST_CACHE[pid] = {
                        "season": season,
                        "hard_hit_percentage": stat.get("hardHitPercentage"),
                        "barrel_percentage": stat.get("barrelPercentage"),
                        "chase_percentage": chase,
                        "whiff_percentage": whiff,
                        "contact_percentage": round(100.0 - whiff, 2) if whiff is not None else None
                    }
        except Exception as e:
            print(f"Error populating Statcast leaderboard cache: {e}")
            _STATCAST_CACHE = {"season_key": season}

    # Extract the requested player from our mapped memory matrix, or provide default blank values
    return _STATCAST_CACHE.get(player_id, {
        "season": season,
        "hard_hit_percentage": None,
        "barrel_percentage": None,
        "chase_percentage": None,
        "whiff_percentage": None,
        "contact_percentage": None
    })
