import requests

def fetch_batter_vs_pitcher_history(batter_id: int, pitcher_id: int):
    """
    Scrapes the exact historical career matchup data between a specific 
    batter and pitcher using their unique MLB ID numbers.
    """
    # StatsAPI endpoint parameters explicitly targeting vsPlayer behavior
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
        f"?stats=vsPlayer&group=hitting&opposingPlayerId={pitcher_id}"
    )
    
    response = requests.get(url)
    
    bvp_payload = {
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "plate_appearances": 0,
        "avg": .000,
        "ops": .000,
        "strikeouts": 0,
        "walks": 0,
        "home_runs": 0,
        "avg_exit_velocity": None
    }
    
    if response.status_code != 200:
        print(f"Error fetching matchup for Hitter:{batter_id} vs Pitcher:{pitcher_id}")
        return bvp_payload
        
    data = response.json()
    stats_list = data.get("stats", [])
    if not stats_list:
        return bvp_payload
        
    splits = stats_list[0].get("splits", [])
    if not splits:
        # No historical matchups recorded between these two players yet
        return bvp_payload
        
    # Extract the total career aggregation metric block
    stat = splits[0].get("stat", {})
    
    bvp_payload.update({
        "plate_appearances": stat.get("plateAppearances", 0),
        "avg": float(stat.get("avg", ".000")),
        "ops": float(stat.get("ops", ".000")),
        "strikeouts": stat.get("strikeOuts", 0),
        "walks": stat.get("baseOnBalls", 0),
        "home_runs": stat.get("homeRuns", 0)
    })
    
    # Advanced Statcast tracking values inside matchup metrics
    # Note: If they haven't faced each other in the Statcast era, this handles a clean fallback
    bvp_payload["avg_exit_velocity"] = stat.get("hitData", {}).get("launchSpeed")
    
    return bvp_payload
