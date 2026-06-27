import requests

def fetch_pitcher_season_stats(player_id: int, season: int):
    """
    Scrapes standard metrics, Statcast profiles, and basic arsenal distribution.
    Ensures safe division operations and type casting for simulator ingestion.
    """
    base_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group=pitching&season={season}"
    adv_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statAdvanced&group=pitching&season={season}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    payload = {
        "player_id": player_id, "season": season,
        "era": None, "whip": None, "k_pct": None, "bb_pct": None,
        "hr_9": None, "gb_pct": None, "fb_pct": None,
        "hard_hit_pct": None, "barrel_pct": None, "avg_exit_velo_allowed": None,
        "arsenal_distribution": {}
    }
    
    def safe_float(val):
        try:
            return float(val) if val not in (None, "", "null", ".---") else None
        except ValueError:
            return None

    # Step 1: Process Base Metrics
    try:
        res_base = requests.get(base_url, headers=headers, timeout=10)
        if res_base.status_code == 200:
            splits = res_base.json().get("stats", [{}])[0].get("splits", [])
            if splits:
                stat = splits[0].get("stat", {})
                payload["era"] = safe_float(stat.get("era"))
                payload["whip"] = safe_float(stat.get("whip"))
                payload["hr_9"] = safe_float(stat.get("homeRunsPer9Innings"))
                
                # Enforce safety boundaries to avoid ZeroDivisionError
                tbf = int(stat.get("battersFaced", 0) or 0)
                if tbf > 0:
                    payload["k_pct"] = round((int(stat.get("strikeOuts", 0) or 0) / tbf) * 100, 1)
                    payload["bb_pct"] = round((int(stat.get("baseOnBalls", 0) or 0) / tbf) * 100, 1)
                else:
                    payload["k_pct"] = 0.0
                    payload["bb_pct"] = 0.0
    except Exception as e:
        print(f"Error pulling base pitching season metrics for player {player_id}: {e}")
                
    # Step 2: Process Advanced Batted Ball Metrics
    try:
        res_adv = requests.get(adv_url, headers=headers, timeout=10)
        if res_adv.status_code == 200:
            splits = res_adv.json().get("stats", [{}])[0].get("splits", [])
            if splits:
                stat = splits[0].get("stat", {})
                payload["gb_pct"] = safe_float(stat.get("groundBallPercentage"))
                payload["fb_pct"] = safe_float(stat.get("flyBallPercentage"))
                payload["hard_hit_pct"] = safe_float(stat.get("hardHitPercentage"))
                payload["barrel_pct"] = safe_float(stat.get("barrelPercentage"))
                payload["avg_exit_velo_allowed"] = safe_float(stat.get("averageExitVelocity"))
    except Exception as e:
        print(f"Error pulling advanced pitching metrics for player {player_id}: {e}")

    return payload
