import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date):
    print(f"Ingesting main boxscore feed matrices for: {target_date}")
    engine = get_engine()
    
    # 1. Fetch the master schedule for the target day
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}"
    try:
        schedule_data = fetch_api_json(url)
        dates = schedule_data.get('dates', [])
        if not dates:
            print(f"Game Feed Alert: No games scheduled by MLB on date {target_date}.")
            return
            
        api_games = dates[0].get('games', [])
        print(f"Game Feed discovered {len(api_games)} games on the MLB schedule API.")
    except Exception as e:
        print(f"CRITICAL: Failed to fetch schedule feed from API: {e}")
        return

    inserted_games = 0

    # 2. Process each game defensively
    for g in api_games:
        game_pk = g.get('gamePk')
        if not game_pk: continue
        
        # Extract teams and venue parameters safely
        venue_id = g.get('venue', {}).get('id')
        home_team_id = g.get('teams', {}).get('home', {}).get('team', {}).get('id')
        away_team_id = g.get('teams', {}).get('away', {}).get('team', {}).get('id')
        
        # Pull game status cleanly
        status_info = g.get('status', {})
        abstract_state = status_info.get('abstractGameState') # Final, Live, Preview
        detailed_state = status_info.get('detailedState')
        
        # LOGGING VERBOSITY: Know exactly what the loop is doing
        print(f"Processing Game ID {game_pk}: Status={detailed_state}, Abstract={abstract_state}")

        # FIX: Ensure we accept all valid variations of a completed game record
        if abstract_state not in ['Final', 'Live', 'Preview'] and detailed_state != 'Final':
            print(f"Skipping Game {game_pk} due to unhandled status flag.")
            continue

        game_data = {
            "game_pk": int(game_pk),
            "game_date": target_date,
            "venue_id": int(venue_id) if venue_id else None,
            "home_team_id": int(home_team_id) if home_team_id else None,
            "away_team_id": int(away_team_id) if away_team_id else None,
            "game_status": detailed_state or abstract_state
        }

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (game_pk, game_date, venue_id, home_team_id, away_team_id, game_status)
                    VALUES (:game_pk, :game_date, :venue_id, :home_team_id, :away_team_id, :game_status)
                    ON CONFLICT (game_pk) DO UPDATE SET
                        game_status = EXCLUDED.game_status,
                        venue_id = EXCLUDED.venue_id;
                """), game_data)
            inserted_games += 1
        except Exception as db_err:
            print(f"Database write failure for Game {game_pk}: {db_err}")

    print(f"Game Feed Complete: Successfully committed {inserted_games} games to the 'games' table.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        print("Error: No target date provided to scrape_game_feed.py")
