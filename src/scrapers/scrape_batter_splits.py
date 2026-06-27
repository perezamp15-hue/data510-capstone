import requests

def fetch_batter_splits(player_id: int, season: int):
    """
    Queries MLB StatsAPI to grab traditional slash lines and extensive context 
    splits (vs handedness, home/away, surface type, and recent timeframes).
    """
    # Clean parameter formatting for the endpoint configuration
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=hitting&type=statSplits&season={season}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    splits_payload = {
        "player_id": player_id,
        "season": season,
        "splits": {
            "vs_lhp": None, "vs_rhp": None, "home": None, "away": None,
            "day": None, "night": None, "grass": None, "turf": None
        }
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout pulling splits for batter {player_id}: {e}")
        return splits_payload
        
    if response.status_code != 200:
        return splits_payload

    data = response.json()
    stats_group = data.get("stats", [])
    if not stats_group:
        return splits_payload
        
    splits = stats_group[0].get("splits", [])
    
    for split in splits:
        sit_code = split.get("split", {}).get("code")
        stat = split.get("stat", {})
        
        # Calculate derived metrics safely
        ab = stat.get("atBats", 0)
        hits = stat.get("hits", 0)
        bb = stat.get("baseOnBalls", 0)
        hbp = stat.get("hitByPitch", 0)
        sf = stat.get("sacrificeFlies", 0)
        hr = stat.get("homeRuns", 0)
        t_bases = stat.get("totalBases", 0)
        k = stat.get("strikeOuts", 0)
        
        iso = (t_bases - hits) / ab if ab > 0 else 0.0
        denom_babip = (ab - k - hr + sf)
        babip = (hits - hr) / denom_babip if denom_babip > 0 else 0.0
        pa = ab + bb + hbp + sf
        bb_pct = (bb / pa) * 100 if pa > 0 else 0.0
        k_pct = (k / pa) * 100 if pa > 0 else 0.0

        metrics = {
            "avg": stat.get("avg"),
            "obp": stat.get("obp"),
            "slg": stat.get("slg"),
            "ops": stat.get("ops"),
            "iso": round(iso, 3),
            "babip": round(babip, 3),
            "bb_percentage": round(bb_pct, 1),
            "k_percentage": round(k_pct, 1)
        }
        
        # Map out required situation targets
        if sit_code == "vl":
            splits_payload["splits"]["vs_lhp"] = metrics
        elif sit_code == "vr":
            splits_payload["splits"]["vs_rhp"] = metrics
        elif sit_code == "h":
            splits_payload["splits"]["home"] = metrics
        elif sit_code == "a":
            splits_payload["splits"]["away"] = metrics
        elif sit_code == "d":
            splits_payload["splits"]["day"] = metrics
        elif sit_code == "n":
            splits_payload["splits"]["night"] = metrics
        elif "grass" in split.get("split", {}).get("description", "").lower():
            splits_payload["splits"]["grass"] = metrics
        elif "turf" in split.get("split", {}).get("description", "").lower():
            splits_payload["splits"]["turf"] = metrics
    
    return splits_payload
