import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date):
    print(f"Ingesting main boxscore feed matrices for: {target_date}")
    engine = get_engine()
    
    # Extract the 4-digit year dynamically from the target date string
    try:
        season_year = int(str(target_date).split("-")[0])
    except Exception:
        season_year = 2026 # Stable fallback for your current system window

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}"
    try:
        schedule_data = fetch_api_json(url)
        dates = schedule_data.get('dates', [])
        if not dates:
            print(f"Game Feed Alert: No games scheduled on date {target_date}.")
            return
            
        api_games = dates[0].get('games', [])
        print(f"Game Feed discovered {len(api_games)} games on the MLB schedule API.")
    except Exception as e:
        print(f"CRITICAL: Failed to fetch schedule feed: {e}")
        return

    inserted_games = 0

    for g in api_games:
        game_pk = g.get('gamePk')
        if not game_pk: continue
        
        api_venue_id = g.get('venue', {}).get('id')
        home_team_id = g.get('teams', {}).get('home', {}).get('team', {}).get('id')
        away_team_id = g.get('teams', {}).get('away', {}).get('team', {}).get('id')
        
        status_info = g.get('status', {})
        abstract_state = status_info.get('abstractGameState')
        detailed_state = status_info.get('detailedState')
        
        if abstract_state not in ['Final', 'Live', 'Preview'] and detailed_state != 'Final':
            continue

        # Map all structural keys including the required season integer
        game_data = {
            "game_pk": int(game_pk),
            "game_date": target_date,
            "season": season_year, # Satisfies the NOT NULL constraint
            "park_id": int(api_venue_id) if api_venue_id else None, 
            "home_team_id": int(home_team_id) if home_team_id else None,
            "away_team_id": int(away_team_id) if away_team_id else None
        }

        try:
            with engine.begin() as conn:
                # Include season in the statement execution
                conn.execute(text("""
                    INSERT INTO games (game_pk, game_date, season, park_id, home_team_id, away_team_id)
                    VALUES (:game_pk, :game_date, :season, :park_id, :home_team_id, :away_team_id)
                    ON CONFLICT (game_pk) DO UPDATE SET
                        park_id = EXCLUDED.park_id,
                        game_date = EXCLUDED.game_date,
                        season = EXCLUDED.season;
                """), game_data)
            inserted_games += 1
        except Exception as db_err:
            print(f"Database write failure for Game {game_pk}: {db_err}")

    print(f"Game Feed Complete: Successfully committed {inserted_games} games to the 'games' table.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        print("Error: No target date provided.")
