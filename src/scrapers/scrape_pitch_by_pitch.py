import requests
import uuid

def verify_and_register_player(conn, player_id: int):
    """Ensures a player exists in the database before processing their play data."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id,))
        if cur.fetchone():
            return # Player is already registered
            
    print(f"Unrecognized player ID {player_id} found in event stream. Registering bio...")
    
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            people = res.json().get("people", [])
            if not people:
                return
            player_data = people[0]
            
            full_name = player_data.get("fullName", f"Unknown Player {player_id}")
            position_code = player_data.get("primaryPosition", {}).get("code", "U")
            bats = player_data.get("batSide", {}).get("code", "R")
            throws = player_data.get("pitchHand", {}).get("code", "R")
            
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO players (player_id, full_name, position_code, bats, throws)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (player_id) DO NOTHING;
                    """,
                    (player_id, full_name, position_code, bats, throws)
                )
                # Let master pipeline handle the commit scope for performance optimization
    except Exception as e:
        print(f"Failed to dynamically register player {player_id}: {e}")

def fetch_game_pitch_by_pitch(conn, game_pk: int):
    """
    Scrapes raw Statcast tracking streams for pitch trajectories.
    Exposes the exact function name required by src/pipeline.py.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/playByPlay"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    plays_extracted = []
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout pulling play-by-play for game {game_pk}: {e}")
        return plays_extracted
        
    if response.status_code != 200:
        return plays_extracted
        
    all_plays = response.json().get("allPlays", [])
    
    for play in all_plays:
        matchup = play.get("matchup", {})
        pitcher_id = matchup.get("pitcher", {}).get("id")
        batter_id = matchup.get("batter", {}).get("id")
        
        if not pitcher_id or not batter_id:
            continue
            
        # Ensure database foreign key integrity on the fly
        verify_and_register_player(conn, pitcher_id)
        verify_and_register_player(conn, batter_id)
        
        events = play.get("playEvents", [])
        for event in events:
            if event.get("isPitch"):
                data = event.get("pitchData", {})
                hit = event.get("hitData", {})
                p_type_obj = data.get("type")
                
                plays_extracted.append({
                    "play_event_id": str(uuid.uuid4()),
                    "game_pk": game_pk,
                    "pitcher_id": pitcher_id,
                    "batter_id": batter_id,
                    "pitch_type": p_type_obj.get("code") if isinstance(p_type_obj, dict) else None,
                    "velocity": data.get("startSpeed"),
                    "exit_velocity": hit.get("launchSpeed") if isinstance(hit, dict) else None,
                    "launch_angle": hit.get("launchAngle") if isinstance(hit, dict) else None,
                    "result": play.get("result", {}).get("description")
                })
                
    return plays_extracted
