import requests
import uuid
# Import your base player scraper module directly
from src.scrapers.scrape_players import fetch_player_bio

def verify_and_register_player(conn, player_id: int):
    """Ensures player exists in foreign key database before raw play data attempts execution."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM players WHERE player_id = %s;", (player_id,))
        if cur.fetchone():
            return # Player verified, safe to proceed
            
    # If not found, fetch live from the API and instantly insert them
    print(f"⚠️ Unrecognized player ID {player_id} discovered in event stream. Registering bio...")
    player_bio = fetch_player_bio(player_id)
    
    if player_bio:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO players (player_id, full_name, position_code, bats, throws)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (player_id) DO NOTHING;
                """,
                (
                    player_bio["player_id"], player_bio["full_name"],
                    player_bio["position_code"], player_bio["bats"], player_bio["throws"]
                )
            )
            conn.commit()

def fetch_game_pitch_by_pitch(conn, game_pk: int):
    """Scrapes raw Statcast tracking streams with an integrated dynamic roster verification layer."""
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
            
        # --- ROSTER INTEGRITY SAFEGUARDS ---
        # Intercept and dynamically append players if missing from database reference layers
        verify_and_register_player(conn, pitcher_id)
        verify_and_register_player(conn, batter_id)
        
        # Safe to process events now that database constraints are validated
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
