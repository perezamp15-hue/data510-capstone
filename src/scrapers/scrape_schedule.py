import requests

def fetch_season_schedule(season: int):
    """
    Queries the global MLB schedule matrix for a full season, 
    mapping out every regular season and postseason matchup game_pk.
    """
    # Query regular season (R) and postseason (P) games for major leagues (sportId=1)
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}&gameTypes=R,P"
    response = requests.get(url)
    
    schedule_payload = []
    
    if response.status_code != 200:
        print(f"Error communicating with MLB Schedule Registry.")
        return schedule_payload
        
    dates = response.json().get("dates", [])
    
    for date_group in dates:
        game_date = date_group.get("date") # Formatted as YYYY-MM-DD
        games = date_group.get("games", [])
        
        for game in games:
            teams = game.get("teams", {})
            home = teams.get("home", {}).get("team", {})
            away = teams.get("away", {}).get("team", {})
            
            schedule_payload.append({
                "game_pk": game.get("gamePk"),
                "season": season,
                "game_date": game_date,
                "home_team_id": home.get("id"),
                "away_team_id": away.get("id"),
                "home_team_name": home.get("name"),
                "away_team_name": away.get("name"),
                "venue_id": game.get("venue", {}).get("id"),
                "status": game.get("status", {}).get("abstractGameState") # 'Preview', 'Live', or 'Final'
            })
            
    return schedule_payload
