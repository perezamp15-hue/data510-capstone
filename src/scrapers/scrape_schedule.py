import requests

def fetch_season_schedule(season: int):
    """
    Queries the global MLB schedule matrix for a full season, 
    mapping out every regular season and postseason matchup game_pk.
    """
    # Query regular season (R) and postseason (P) games for major leagues (sportId=1)
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}&gameTypes=R,P"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    schedule_payload = []
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Error communicating with MLB Schedule Registry (Status: {response.status_code}).")
            return schedule_payload
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching full season schedule for {season}: {e}")
        return schedule_payload
        
    dates = response.json().get("dates", [])
    
    for date_group in dates:
        game_date = date_group.get("date") # Formatted as YYYY-MM-DD
        games = date_group.get("games", [])
        
        for game in games:
            game_pk = game.get("gamePk")
            if not game_pk:
                continue
                
            teams = game.get("teams", {})
            home = teams.get("home", {}).get("team", {})
            away = teams.get("away", {}).get("team", {})
            venue_id = game.get("venue", {}).get("id")
            
            schedule_payload.append({
                "game_pk": int(game_pk),
                "season": int(season),
                "game_date": game_date,
                "home_team_id": int(home["id"]) if home.get("id") else None,
                "away_team_id": int(away["id"]) if away.get("id") else None,
                "home_team_name": home.get("name"),
                "away_team_name": away.get("name"),
                "venue_id": int(venue_id) if venue_id else None,
                "status": game.get("status", {}).get("abstractGameState") # 'Preview', 'Live', or 'Final'
            })
            
    return schedule_payload
