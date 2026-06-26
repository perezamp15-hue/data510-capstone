import requests
import uuid
# from src.scrapers.scrape_players import fetch_team_roster

def verify_and_register_player(conn, player_id: int):
    """Ensures a player exists in the database before processing their play data."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id,))
        if cur.fetchone():
            return # Player is already registered
            
    print(f"Unrecognized player ID {player_id} found in event stream. Registering bio...")
    # Fallback/dynamic insertion registration if a rookie or call-up appears
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        res = requests.get(url)
        if res.status_code == 200:
            player_data = res.json().get("people", [{}])[0]
            full_name = player_data.get("fullName", "Unknown Player")
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
                conn.commit()
    except Exception as e:
        print(f"Failed to dynamically register player {player_id}: {e}")

def fetch_game_pitch_by_pitch(conn, game_pk: int):
    """
    Scrapes raw Statcast tracking streams for pitch trajectories.
    Exposes the exact function name required by src/pipeline.py.
    """
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/playByPlay"
    response = requests.get(url)
    plays_extracted = []
    
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
        for idx, event in enumerate(events):
            if event.get("isPitch"):
                data = event.get("pitchData", {})
                hit = event.get("hitData", {})
                
                plays_extracted.append({
                    "play_event_id": str(uuid.uuid4()),
                    "game_pk": game_pk,
                    "pitcher_id": pitcher_id,
                    "batter_id": batter_id,
                    "pitch_type": data.get("type", {}).get("code"),
                    "velocity": data.get("startSpeed"),
                    "exit_velocity": hit.get("launchSpeed"),
                    "launch_angle": hit.get("launchAngle"),
                    "result": play.get("result", {}).get("description")
                })
                
    return plays_extracted
