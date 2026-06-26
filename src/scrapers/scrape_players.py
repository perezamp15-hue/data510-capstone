import requests

def fetch_team_roster(team_id: int, season: int = 2026):
    """
    Fetches all players on a given team's roster for a specific season,
    including their unique MLB ID numbers and core biographical attributes.
    """
    # MLB StatsAPI roster endpoint
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=allSeason&season={season}"
    response = requests.get(url)
    
    player_roster = []
    if response.status_code != 200:
        print(f"Failed to fetch roster for team {team_id}")
        return []
        
    data = response.json()
    roster_list = data.get("roster", [])
    
    for row in roster_list:
        person = row.get("person", {})
        position = row.get("position", {})
        
        player_payload = {
            "player_id": person.get("id"),          # Canonical MLB ID Number
            "full_name": person.get("fullName"),
            "jersey_number": row.get("jerseyNumber"),
            "position_code": position.get("code"),  # e.g., '1' for Pitcher, '10' for DH
            "position_type": position.get("type"),  # e.g., 'Pitcher', 'Batter'
            "status_code": row.get("status", {}).get("code") # e.g., 'A' for Active
        }
        
        # Hydrate deeper biographical attributes per player (Handedness is vital for splits!)
        bio_url = f"https://statsapi.mlb.com/api/v1/people/{player_payload['player_id']}"
        bio_res = requests.get(bio_url)
        
        if bio_res.status_code == 200:
            bio_data = bio_res.json().get("people", [{}])[0]
            player_payload.update({
                "bats": bio_data.get("batSide", {}).get("code"),      # 'R', 'L', or 'S'
                "throws": bio_data.get("pitchHand", {}).get("code"),  # 'R' or 'L'
                "birth_date": bio_data.get("birthDate"),
                "height": bio_data.get("height"),
                "weight": bio_data.get("weight")
            })
            
        player_roster.append(player_payload)
        
    return player_roster

def fetch_all_mlb_teams(season: int = 2026):
    """
    Helper function to get all active MLB team IDs so you can loop 
    through them and grab every roster in the league.
    """
    url = f"https://statsapi.mlb.com/api/v1/teams?sportId=1&season={season}"
    response = requests.get(url)
    if response.status_code != 200:
        return []
        
    teams = response.json().get("teams", [])
    return [{"team_id": t.get("id"), "team_name": t.get("name")} for t in teams]
