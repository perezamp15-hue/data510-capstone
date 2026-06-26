import requests

def fetch_player_splits(player_id: int, season: int, group: str = "hitting"):
    """
    Fetches extensive situational splits for a player.
    group: 'hitting' or 'pitching'
    """
    # Hydrating 'statSplits' brings down vsLHP, vsRHP, home, away, lastXDays, etc.
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statSplits&group={group}&season={season}"
    response = requests.get(url)
    
    if response.status_code != 200:
        return []
        
    data = response.json()
    splits_extracted = []
    
    for stat_type in data.get("stats", []):
        for split in stat_type.get("splits", []):
            split_info = split.get("split", {})
            stats = split.get("stat", {})
            
            split_record = {
                "player_id": player_id,
                "season": season,
                "split_name": split_info.get("name"), # e.g., "vs Left", "Home", "Last 30 Days"
                "split_code": split_info.get("code"),
                "games_played": stats.get("gamesPlayed"),
                "plate_appearances": stats.get("plateAppearances"),
                "avg": stats.get("avg"),
                "obp": stats.get("obp"),
                "slg": stats.get("slg"),
                "ops": stats.get("ops"),
                "home_runs": stats.get("homeRuns"),
                "strikeouts": stats.get("strikeouts"),
                "walks": stats.get("baseOnBalls")
            }
            splits_extracted.append(split_record)
            
    return splits_extracted
