import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        
    print(f"Ingesting main boxscore feed matrices for: {target_date}")
    engine = get_engine()
    
    # 1. Fetch games scheduled for this date from the master schedule API
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={target_date}"
    try:
        schedule_data = fetch_api_json(url)
        dates_node = schedule_data.get('dates', [])
        if not dates_node:
            print(f"No scheduled games found on MLB API for date: {target_date}")
            return
        games_list = dates_node[0].get('games', [])
    except Exception as e:
        print(f"Failed to fetch schedule feed for {target_date}: {e}")
        return

    print(f"Game Feed discovered {len(games_list)} games on the MLB schedule API.")
    games_saved = 0

    # 2. Loop through daily games and populate the primary table matrix
    for game in games_list:
        pk = game.get('gamePk')
        if not pk:
            continue
            
        home_node = game.get('teams', {}).get('home', {})
        away_node = game.get('teams', {}).get('away', {})
        
        # --- DYNAMIC METRIC EXTRACTION ---
        # 1. Extract and process game duration safely
        duration_minutes = None
        game_length_str = game.get('status', {}).get('gameActualLength') # Often stored here or in linescore
        
        if not game_length_str:
            # Fallback check inside game context if the status block hasn't updated it yet
            game_length_str = game.get('gameLength')

        if game_length_str:
            try:
                if ":" in str(game_length_str):
                    parts = str(game_length_str).split(":")
                    duration_minutes = int(parts[0]) * 60 + int(parts[1])
                else:
                    duration_minutes = int(game_length_str)
            except (ValueError, IndexError):
                duration_minutes = None

        # 2. Extract attendance safely
        attendance_val = game.get('attendance')
        attendance_int = int(attendance_val) if attendance_val else None

        game_dict = {
            "game_pk": int(pk),
            "game_date": target_date,
            "game_type": game.get('gameType', 'R'),
            "season": int(game.get('season', 2026)),
            "home_team_id": int(home_node.get('team', {}).get('id')),
            "away_team_id": int(away_node.get('team', {}).get('id')),
            "venue_id": int(game.get('venue', {}).get('id')),
            "home_score": int(home_node.get('score', 0)) if home_node.get('score') is not None else None,
            "away_score": int(away_node.get('score', 0)) if away_node.get('score') is not None else None,
            "game_status": game.get('status', {}).get('abstractGameState', 'Final'),
            "attendance": attendance_int,
            "game_duration_minutes": duration_minutes
        }

        # Safe relational execution context block
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, game_type, season, home_team_id, 
                        away_team_id, venue_id, home_score, away_score, game_status,
                        attendance, game_duration_minutes
                    )
                    VALUES (
                        :game_pk, :game_date, :game_type, :season, :home_team_id, 
                        :away_team_id, :venue_id, :home_score, :away_score, :game_status,
                        :attendance, :game_duration_minutes
                    )
                    ON CONFLICT (game_pk) DO UPDATE SET
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        game_status = EXCLUDED.game_status,
                        attendance = EXCLUDED.attendance,
                        game_duration_minutes = EXCLUDED.game_duration_minutes;
                """), game_dict)
            games_saved += 1
        except Exception as e:
            print(f"Failed to write boxscore index for game {pk}: {e}")
            continue

    print(f"Game Feed Complete: Successfully saved {games_saved} games with attendance and duration telemetry.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
