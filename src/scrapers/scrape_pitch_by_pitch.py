import requests

def fetch_pitch_by_pitch(game_pk: int):
    """
    Fetches granular Statcast data, coordinates, breaks, and velocities 
    for every pitch thrown in a specific game ID.
    """
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    response = requests.get(url)
    
    if response.status_code != 200:
        return []
        
    data = response.json()
    all_plays = data.get("liveData", {}).get("plays", {}).get("allPlays", [])
    pitches_extracted = []
    
    for play in all_plays:
        about = play.get("about", {})
        count = play.get("count", {})
        matchup = play.get("matchup", {})
        
        inning = about.get("inning")
        is_top = about.get("isTopInning")
        batter_id = matchup.get("batter", {}).get("id")
        pitcher_id = matchup.get("pitcher", {}).get("id")
        
        for event in play.get("playEvents", []):
            if event.get("isPitch"):
                pitch_data = event.get("pitchData", {})
                details = event.get("details", {})
                
                pitch_record = {
                    "game_pk": game_pk,
                    "play_index": event.get("index"),
                    "inning": inning,
                    "is_top_inning": is_top,
                    "batter_id": batter_id,
                    "pitcher_id": pitcher_id,
                    "balls_before": count.get("balls"),
                    "strikes_before": count.get("strikes"),
                    "pitch_type": details.get("type", {}).get("code"),
                    "velocity": pitch_data.get("startSpeed"),
                    "spin_rate": pitch_data.get("breaks", {}).get("spinRate"),
                    "vert_break": pitch_data.get("breaks", {}).get("breakVertical"),
                    "horiz_break": pitch_data.get("breaks", {}).get("breakHorizontal"),
                    "zone_location": pitch_data.get("zone"),
                    "description": details.get("description"), # e.g., Called Strike, Ball, Fowl, In play
                    "call_code": details.get("code")
                }
                pitches_extracted.append(pitch_record)
                
    return pitches_extracted
