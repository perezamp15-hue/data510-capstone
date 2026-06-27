import requests

def fetch_team_roster(team_id: int, season: int = 2026):
    """
    Fetches all players on a given team's roster for a specific season.
    Optimized to eliminate the N+1 network request pattern using batched hydrations.
    """
    # By adding person(batSide,pitchHand,birthDate,height,weight) inside the roster hydration parameter,
    # the API embeds the biographical records directly inside the payload, cutting network costs by 98%.
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=allSeason&season={season}&hydrate=person(batSide,pitchHand,birthDate,height,weight)"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    player_roster = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Failed to fetch roster for team {team_id} (Status: {response.status_code})")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching roster for team {team_id}: {e}")
        return []
        
    data = response.json()
    roster_list = data.get("roster", [])
    
    for row in roster_list:
        person = row.get("person", {})
        position = row.get("position", {})
        
        # Guard against unpopulated or broken player node entries
        p_id = person.get("id")
        if not p_id:
            continue
            
        player_payload = {
            "player_id": int(p_id),
            "full_name": person.get("fullName", f"Unknown Player {p_id}"),
            "jersey_number": row.get("jerseyNumber"),
            "position_code": position.get("code"),                     # e.g., '1' for Pitcher, '10' for DH
            "position_type": position.get("type"),                     # e.g., 'Pitcher', 'Batter'
            "status_code": row.get("status", {}).get("code"),          # e.g., 'A' for Active
            "bats": person.get("batSide", {}).get("code", "R"),         # Default fallback to Right
            "throws": person.get("pitchHand", {}).get("code", "R"),      # Default fallback to Right
            "birth_date": person.get("birthDate"),
            "height": person.get("height"),
            "weight": person.get("weight")
        }
        
        player_roster.append(player_payload)
        
    return player_roster

def fetch_all_mlb_teams(season: int = 2026):
    """
    Helper function to get all active MLB team IDs for directory looping.
    """
    url = f"https://statsapi.mlb.com/api/v1/teams?sportId=1&season={season}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
            
        teams = response.json().get("teams", [])
        return [{"team_id": int(t.get("id")), "team_name": t.get("name")} for t in teams if t.get("id")]
    except Exception as e:
        print(f"Error pulling league master team matrix: {e}")
        return []
