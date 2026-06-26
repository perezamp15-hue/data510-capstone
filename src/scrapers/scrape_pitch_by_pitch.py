import requests
import uuid

def fetch_pitch_by_pitch_data(game_pk: int):
    """
    Scrapes hyper-detailed Statcast metrics for every single pitch thrown 
    in a given game using its unique game_pk.
    
    Returns:
        list: A list of dictionaries, where each dict represents one individual pitch.
    """
    # Hits MLB's comprehensive live feed endpoint for play-by-play timelines
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
    response = requests.get(url)
    
    if response.status_code != 200:
        print(f"Failed to fetch live feed for game {game_pk}")
        return []
        
    data = response.json()
    all_plays = data.get("liveData", {}).get("plays", {}).get("allPlays", [])
    
    scraped_pitches = []
    
    # Loop through every Plate Appearance (At-Bat) in the game
    for play in all_plays:
        about = play.get("about", {})
        inning = about.get("inning")
        half_inning = about.get("halfInning") # 'top' or 'bottom'
        at_bat_index = about.get("atBatIndex")
        
        matchup = play.get("matchup", {})
        pitcher_id = matchup.get("pitcher", {}).get("id")
        batter_id = matchup.get("batter", {}).get("id")
        
        # Loop through every event inside this single At-Bat
        play_events = play.get("playEvents", [])
        for event in play_events:
            # We only care about events that are actual pitches thrown to a batter
            if not event.get("isPitch", False):
                continue
                
            pitch_data = event.get("pitchData", {})
            hit_data = event.get("hitData", {})
            details = event.get("details", {})
            
            # Identify swing and contact states based on pitch description text
            description = details.get("description", "").lower()
            
            # Logical flag evaluations for your simulation engine
            is_swing = any(x in description for x in ["swinging", "foul", "in play"])
            is_contact = any(x in description for x in ["foul", "in play"])
            
            # Combine everything into a clean, flat dictionary structure
            pitch_payload = {
                "game_pk": game_pk,
                "at_bat_index": at_bat_index,
                "pitch_number": event.get("pitchNumber"),
                "inning": inning,
                "half_inning": half_inning,
                "pitcher_id": pitcher_id,
                "batter_id": batter_id,
                
                # --- Pitch Type & Profiles ---
                "pitch_type": details.get("type", {}).get("code"), # e.g., 'FF', 'SL', 'CH'
                "velocity": pitch_data.get("startSpeed"),           # Release Velocity
                "spin_rate": pitch_data.get("spinRate"),           # Spin Rate (RPM)
                
                # --- Trajectory Breaks ---
                "vertical_break": pitch_data.get("breaks", {}).get("breakVertical"),
                "horizontal_break": pitch_data.get("breaks", {}).get("breakHorizontal"),
                
                # --- Release Variables ---
                "release_height": pitch_data.get("coordinates", {}).get("z0"), # z0 is release height in feet
                "release_side": pitch_data.get("coordinates", {}).get("x0"),   # x0 is release side vector
                "extension": pitch_data.get("extension"),                      # Extension (ft)
                
                # --- Strike Zone Plate Location ---
                "plate_loc_x": pitch_data.get("coordinates", {}).get("pX"), # Horizontal intersection (ft)
                "plate_loc_z": pitch_data.get("coordinates", {}).get("pZ"), # Height intersection (ft)
                
                # --- Action Checkpoints ---
                "batter_swing": is_swing,
                "contact": is_contact,
                
                # --- Batted Ball Data (Only populates if contact was made/put in play) ---
                "exit_velocity": hit_data.get("launchSpeed"),
                "launch_angle": hit_data.get("launchAngle"),
                "hit_distance": hit_data.get("totalDistance"),
                
                # --- Final Result ---
                "result": details.get("description"), # e.g., "Swinging Strike", "Ball", "In play, run(s)"
                "play_event_id": event.get("playId")  # Unique string UUID for the unique pitch event
            }
            
            scraped_pitches.append(pitch_payload)
            
    return scraped_pitches
