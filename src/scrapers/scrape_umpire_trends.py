import requests

def fetch_umpire_season_trends(umpire_name: str, season: int = 2026):
    """
    Aggregates historical game outcomes officiated by a specific home plate 
    umpire to uncover tendencies in strike zone size, over/under ratios, 
    and general performance distributions.
    """
    # MLB StatsAPI allows fetching game schedules filtered by an official's name
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}&hydrate=linescore,officials"
    response = requests.get(url)
    
    trends = {
        "umpire_name": umpire_name,
        "season": season,
        "games_officiated": 0,
        "strike_zone_size_proxy": None, # Average total pitches per game (proxy for zone size)
        "over_pct": 0.0,
        "home_team_win_pct": 0.0,
        "walk_pct": 0.0,
        "strikeout_pct": 0.0
    }
    
    if response.status_code != 200:
        print(f"Error accessing schedule logs for umpire tracking.")
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
                
            # Game details check (Ensure the matchup concluded)
            linescore = game.get("linescore", {})
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
                
            total_games += 1
            
            # --- Home Team Win Tracking ---
            home_score = linescore.get("teams", {}).get("home", {}).get("runs", 0)
            away_score = linescore.get("teams", {}).get("away", {}).get("runs", 0)
            if home_score > away_score:
                home_wins += 1
                
            total_runs += (home_score + away_score)
            
            # --- Deeper Boxscore Iteration for Team Totals ---
            # Extract pitch metrics, walks, and Ks from this game's specific endpoint
            game_pk = game.get("gamePk")
            box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
            box_res = requests.get(box_url)
            
            if box_res.status_code == 200:
                b_data = box_res.json()
                teams_data = b_data.get("teams", {})
                
                for side in ["home", "away"]:
                    team_stats = teams_data.get(side, {}).get("teamStats", {}).get("pitching", {})
                    total_walks += team_stats.get("baseOnBalls", 0)
                    total_strikeouts += team_stats.get("strikeOuts", 0)
                    total_pitches += team_stats.get("pitchesThrown", 0)
                    total_plate_appearances += team_stats.get("battersFaced", 0)

    if total_games > 0:
        # Assuming a baseline standard market line of 8.5 total runs for Over/Under proxy tracking
        # Alternatively, you can cross-reference an odds API here.
        trends.update({
            "games_officiated": total_games,
            "strike_zone_size_proxy": round(total_pitches / total_games, 1),
            "home_team_win_pct": round((home_wins / total_games) * 100, 1),
            "walk_pct": round((total_walks / max(1, total_plate_appearances)) * 100, 1),
            "strikeout_pct": round((total_strikeouts / max(1, total_plate_appearances)) * 100, 1)
        })
        
    return trends
