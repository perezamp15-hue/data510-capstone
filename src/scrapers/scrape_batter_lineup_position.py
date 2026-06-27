import requests

def fetch_lineup_positions(player_id: int, season: int):
    """
    Scrapes a batter's statistical performance broken down by their 
    position in the batting order (1st, 2nd, ... 9th spot) for a given season.
    """
    # StatsAPI endpoint using lineUpSplits configuration
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        f"?stats=statSplits&group=hitting&sitCodes=bo1,bo2,bo3,bo4,bo5,bo6,bo7,bo8,bo9&season={season}"
    )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout pulling lineup splits for batter {player_id}: {e}")
        return {
            "player_id": player_id,
            "season": season,
            "lineup_positions": {i: {"games": 0, "plate_appearances": 0, "pa_per_game": 0.0, "rbi": 0, "hr": 0} for i in range(1, 10)}
        }
    
    # Pre-structure dictionary to hold metrics for all 9 spots in the order
    lineup_payload = {
        "player_id": player_id,
        "season": season,
        "lineup_positions": {i: {"games": 0, "plate_appearances": 0, "pa_per_game": 0.0, "rbi": 0, "hr": 0} for i in range(1, 10)}
    }
    
    if response.status_code != 200:
        print(f"Error pulling lineup splits for batter {player_id} (Status: {response.status_code})")
        return lineup_payload
        
    data = response.json()
    stats_list = data.get("stats", [])
    if not stats_list:
        return lineup_payload
        
    splits = stats_list[0].get("splits", [])
    
    for split in splits:
        code = split.get("split", {}).get("code")  # 'bo1' = 1st spot, 'bo2' = 2nd spot, etc.
        stat = split.get("stat", {})
        
        # Extract order spot integer from code string (e.g., "bo3" -> 3)
        try:
            spot_num = int(code.replace("bo", ""))
        except (ValueError, AttributeError):
            continue
            
        games = stat.get("games", 0)
        plate_apps = stat.get("plateAppearances", 0)
        
        metrics = {
            "games": games,
            "plate_appearances": plate_apps,
            # Calculate average Plate Appearances per Game in this specific slot
            "pa_per_game": round(plate_apps / games, 2) if games > 0 else 0.0,
            # RBI and HR track the realized run-production environment of the slot
            "rbi": stat.get("rbi", 0),
            "hr": stat.get("homeRuns", 0)
        }
        
        lineup_payload["lineup_positions"][spot_num] = metrics

    return lineup_payload
