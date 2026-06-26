import requests

def fetch_batter_pitch_type_splits(player_id: int, season: int):
    """
    Scrapes a batter's metrics against discrete pitch types (Fastball, Slider, etc.)
    including modern plate discipline profiles and tracking values.
    """
    # StatsAPI pitch-type split configuration endpoint
    url = (
        f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        f"?stats=statSplits&group=hitting&sitCodes=pFT,pSL,pCU,pCH,pSI&season={season}"
    )
    
    response = requests.get(url)
    
    # Pre-structure dictionary for standard target tracking arrays
    # Mapping keys directly match MLB pitch types codes:
    # FT/FF/SI (Fastball/Sinker), SL (Slider), CU (Curveball), CH (Changeup)
    pitch_type_splits = {
        "player_id": player_id,
        "season": season,
        "pitch_stats": {
            "Fastball": {"avg": .000, "slg": .000, "whiff_pct": None, "chase_pct": None, "xwoba": None},
            "Slider":   {"avg": .000, "slg": .000, "whiff_pct": None, "chase_pct": None, "xwoba": None},
            "Curve":    {"avg": .000, "slg": .000, "whiff_pct": None, "chase_pct": None, "xwoba": None},
            "Change":   {"avg": .000, "slg": .000, "whiff_pct": None, "chase_pct": None, "xwoba": None},
            "Sinker":   {"avg": .000, "slg": .000, "whiff_pct": None, "chase_pct": None, "xwoba": None}
        }
    }
    
    if response.status_code != 200:
        print(f"Error pulling pitch type splits for batter {player_id}")
        return pitch_type_splits
        
    data = response.json()
    stats_list = data.get("stats", [])
    if not stats_list:
        return pitch_type_splits
        
    splits = stats_list[0].get("splits", [])
    
    for split in splits:
        code = split.get("split", {}).get("code") # Situation/Pitch identifier code
        stat = split.get("stat", {})
        
        metrics = {
            "avg": float(stat.get("avg", ".000")),
            "slg": float(stat.get("slg", ".000")),
            "whiff_pct": stat.get("whiffPercentage"),
            "chase_pct": stat.get("plateDiscipline", {}).get("chasePercentage"),
            "xwoba": stat.get("expectedMetrics", {}).get("xwoba")
        }
        
        # Map back to our cleaner simulator dictionary format
        if code in ["pFT", "pFF"]:  # Fastballs
            pitch_type_splits["pitch_stats"]["Fastball"] = metrics
        elif code == "pSL":        # Sliders
            pitch_type_splits["pitch_stats"]["Slider"] = metrics
        elif code == "pCU":        # Curveballs
            pitch_type_splits["pitch_stats"]["Curve"] = metrics
        elif code == "pCH":        # Changeups
            pitch_type_splits["pitch_stats"]["Change"] = metrics
        elif code == "pSI":        # Sinkers
            pitch_type_splits["pitch_stats"]["Sinker"] = metrics

    return pitch_type_splits
