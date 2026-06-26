import requests

def fetch_detailed_injury_reports(sport_id: int = 1):
    """
    Scrapes full medical status summaries, transaction injury trackers, 
    and detailed day-to-day notes across the league.
    """
    # Queries general player tracking with a status hydration for precise injury strings
    url = f"https://statsapi.mlb.com/api/v1/sports/{sport_id}/players?hydrate=currentStatus"
    response = requests.get(url)
    
    injury_reports = []
    if response.status_code != 200:
        return injury_reports
        
    players = response.json().get("people", [])
    
    for player in players:
        status = player.get("currentStatus", {})
        # Filter for players marked with an active injury flag or custom designation
        if status.get("injuryDesignation") or "injured" in status.get("description", "").lower():
            
            note = status.get("description", "")
            # Determine dynamic simulator categories based on semantic analysis
            category = "IL"
            if "day-to-day" in note.lower() or "questionable" in note.lower():
                category = "Questionable"
            elif "probable" in note.lower():
                category = "Probable"
            elif "rehab" in note.lower() or "returning" in note.lower():
                category = "Returning from Injury"
                
            injury_reports.append({
                "player_id": player.get("id"),
                "player_name": player.get("fullName"),
                "injury_designation": status.get("injuryDesignation"), # e.g., "7-day IL"
                "status_category": category,                           # Simulator assignment
                "medical_note": note,                                  # Exact text report string
                "date_updated": player.get("lastPlayedDate")          # Baseline proxy timestamp
            })
            
    return injury_reports
