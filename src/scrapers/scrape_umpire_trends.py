import requests

def fetch_umpire_trends(umpire_name: str, season: int):
    """
    Aggregates historical game outcomes officiated by a specific home plate 
    umpire to uncover tendencies in strike zone size, over/under ratios, 
    and general performance distributions.
    
    Optimized to fetch all nested team stats in a single batched API payload.
    """
    # FIXED: Added boxscore(pitching) hydration to eliminate N+1 sub-requests entirely
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}&hydrate=linescore,officials,boxscore(pitching)"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    trends = {
        "umpire_name": umpire_name,
        "season": season,
        "games_officiated": 0,
        "strike_zone_size_proxy": None,  # Average total pitches per game (proxy for zone size)
        "home_team_win_pct": 0.0,
        "walk_pct": 0.0,
        "strikeout_pct": 0.0
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code != 200:
            print(f"Error accessing schedule logs for umpire tracking.")
            return trends
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching umpire schedules: {e}")
        return trends
        
    data = response.json()
    dates = data.get("dates", [])
    
    total_games = 0
    home_wins = 0
    total_runs = 0
    total_walks = 0
    total_strikeouts = 0
    total_pitches = 0
    total_plate_appearances = 0
    
    # Iterate through all scheduled days in the season
    for date_node in dates:
        for game in date_node.get("games", []):
            # Verify if this specific umpire was behind home plate for this matchup
            is_home_plate = False
            for official in game.get("officials", []):
                if (official.get("official", {}).get("fullName") == umpire_name and 
                    official.get("officialType", {}).get("description") == "Home Plate"):
                    is_home_plate = True
                    break
                    
            if not is_home_plate:
                continue
                
            # Ensure the matchup concluded
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
                
            linescore = game.get("linescore", {})
            total_games += 1
            
            # --- Home Team Win Tracking ---
            home_score = int(linescore.get("teams", {}).get("home", {}).get("runs", 0) or 0)
            away_score = int(linescore.get("teams", {}).get("away", {}).get("runs", 0) or 0)
            if home_score > away_score:
                home_wins += 1
                
            total_runs += (home_score + away_score)
            
            # --- Bulk Hydrated Boxscore Processing (No Extra HTTP Requests Required) ---
            teams_data = game.get("boxscore", {}).get("teams", {})
            
            for side in ["home", "away"]:
                team_stats = teams_data.get(side, {}).get("teamStats", {}).get("pitching", {})
                
                total_walks += int(team_stats.get("baseOnBalls", 0) or 0)
                total_strikeouts += int(team_stats.get("strikeOuts", 0) or 0)
                total_pitches += int(team_stats.get("pitchesThrown", 0) or 0)
                total_plate_appearances += int(team_stats.get("battersFaced", 0) or 0)

    if total_games > 0:
        trends.update({
            "games_officiated": total_games,
            "strike_zone_size_proxy": round(total_pitches / total_games, 1),
            "home_team_win_pct": round((home_wins / total_games) * 100, 1),
            "walk_pct": round((total_walks / max(1, total_plate_appearances)) * 100, 1),
            "strikeout_pct": round((total_strikeouts / max(1, total_plate_appearances)) * 100, 1)
        })
        
    return trends
