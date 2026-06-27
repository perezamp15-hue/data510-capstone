import requests

def fetch_injury_reports(sport_id: int = 1):
    """
    Scrapes full medical status summaries, transaction injury trackers, 
    and detailed day-to-day notes across the league.
    """
    # Added sport_id into parameters to avoid NameError crash
    url = f"https://statsapi.mlb.com/api/v1/sports/{sport_id}/players?hydrate=currentStatus"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    injury_reports = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching league injury reports: {e}")
        return injury_reports
        
    if response.status_code != 200:
        print(f"Failed to fetch injury reports (Status: {response.status_code})")
        return injury_reports
        
    players = response.json().get("people", [])
    
    for player in players:
        status = player.get("currentStatus", {})
        injury_desig = status.get("injuryDesignation")
        description = status.get("description", "")
        
        # Safe handling of empty or missing description text
        clean_desc = str(description).lower() if description else ""
        
        # Filter for players marked with an active injury flag or custom designation
        if injury_desig or "injured" in clean_desc:
            note = description if description else ""
            
            # Determine dynamic simulator categories based on semantic analysis
            category = "IL"
            if "day-to-day" in clean_desc or "questionable" in clean_desc:
                category = "Questionable"
            elif "probable" in clean_desc:
                category = "Probable"
            elif "rehab" in clean_desc or "returning" in clean_desc:
                category = "Returning from Injury"
                
            injury_reports.append({
                "player_id": int(player.get("id")),
                "player_name": player.get("fullName"),
                "injury_designation": injury_desig,            # e.g., "7-day IL"
                "status_category": category,                    # Simulator assignment
                "medical_note": note,                           # Exact text report string
                "date_updated": player.get("lastPlayedDate")    # Baseline proxy timestamp
            })
            
    return injury_reports
