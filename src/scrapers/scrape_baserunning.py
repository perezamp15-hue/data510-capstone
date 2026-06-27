import requests

def fetch_baserunning_stats(player_id: int, season: int):
    """
    Scrapes baseline and advanced base running metrics for a player, 
    including tracking properties like sprint speed and extra bases taken.
    """
    # 1. Standard Hitting endpoint for Stolen Bases
    base_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group=hitting&season={season}"
    
    # 2. Advanced endpoint for baserunning advancement tracking (XBT%, 1st-to-3rd%)
    adv_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statAdvanced&group=hitting&season={season}"

    payload = {
        "player_id": player_id,
        "season": season,
        "stolen_bases": 0,
        "success_rate": 0.0,
        "sprint_speed": None,          # Ft/sec, fallback if not qualified
        "extra_bases_taken_pct": 0.0,   # XBT%
        "first_to_third_pct": 0.0
    }

    # Process Standard Metrics (SB and CS)
    res_base = requests.get(base_url)
    if res_base.status_code == 200:
        splits = res_base.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            sb = stat.get("stolenBases", 0)
            cs = stat.get("caughtStealing", 0)
            attempts = sb + cs
            
            payload["stolen_bases"] = sb
            payload["success_rate"] = round((sb / attempts) * 100, 1) if attempts > 0 else 0.0

    # Process Advanced Baserunning Metrics
    res_adv = requests.get(adv_url)
    if res_adv.status_code == 200:
        splits = res_adv.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            
            # StatAdvanced provides base advancement metrics natively
            payload["extra_bases_taken_pct"] = stat.get("extraBasesTakenPercentage", 0.0)
            payload["first_to_third_pct"] = stat.get("firstToThirdPercentage", 0.0)
            
            # Sprint speed is historically mapped in advanced metrics or through Savant tracker exports
            payload["sprint_speed"] = stat.get("sprintSpeed") 

    return payload
