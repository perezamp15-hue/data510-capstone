import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date):
    print(f"Ingesting main boxscore feed matrices for: {target_date}")
    engine = get_engine()
    
    try:
        season_year = int(str(target_date).split("-")[0])
    except Exception:
        season_year = 2026

    # Fetch with hydration to grab deep game linescore and boxscore metadata
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}&hydrate=linescore,boxscore"
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
        
        status_info = g.get('status', {})
        abstract_state = status_info.get('abstractGameState')
        detailed_state = status_info.get('detailedState')
        
        if abstract_state not in ['Final', 'Live', 'Preview'] and detailed_state != 'Final':
            continue

        # Core Keys
        game_type = g.get('gameType', 'R') 
        api_venue_id = g.get('venue', {}).get('id')
        
        home_node = g.get('teams', {}).get('home', {})
        away_node = g.get('teams', {}).get('away', {})
        
        home_team_id = home_node.get('team', {}).get('id')
        away_team_id = away_node.get('team', {}).get('id')

        # Boxscore stats
        day_night_type = g.get('dayNight')
        game_info = g.get('boxscore', {}).get('info', [])
        attendance = None
        duration_mins = None
        
        for info in game_info:
            label = info.get('label', '')
            value = info.get('value', '')
            if 'Attendance' in label:
                try: attendance = int(value.replace(',', ''))
                except: pass
            if 'T' in label or 'Duration' in label:
                try:
                    parts = value.split(':')
                    duration_mins = int(parts[0]) * 60 + int(parts[1])
                except: pass

        # Boxscore Scores
        linescore = g.get('linescore', {})
        home_score = linescore.get('teams', {}).get('home', {}).get('runs')
        away_score = linescore.get('teams', {}).get('away', {}).get('runs')

        # Clean mapping with NO 'is_tie' field
        game_data = {
            "game_pk": int(game_pk),
            "game_date": target_date,
            "season": season_year,
            "game_type": game_type,
            "park_id": int(api_venue_id) if api_venue_id else None, 
            "home_team_id": int(home_team_id) if home_team_id else None,
            "away_team_id": int(away_team_id) if away_team_id else None,
            "day_night_type": day_night_type,
            "attendance": attendance,
            "game_duration_minutes": duration_mins,
            "home_score": home_score,
            "away_score": away_score
        }

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, season, game_type, park_id, 
                        home_team_id, away_team_id, day_night_type, 
                        attendance, game_duration_minutes, home_score, away_score
                    )
                    VALUES (
                        :game_pk, :game_date, :season, :game_type, :park_id, 
                        :home_team_id, :away_team_id, :day_night_type, 
                        :attendance, :game_duration_minutes, :home_score, :away_score
                    )
                    ON CONFLICT (game_pk) DO UPDATE SET
                        park_id = EXCLUDED.park_id,
                        game_date = EXCLUDED.game_date,
                        season = EXCLUDED.season,
                        game_type = EXCLUDED.game_type,
                        day_night_type = EXCLUDED.day_night_type,
                        attendance = EXCLUDED.attendance,
                        game_duration_minutes = EXCLUDED.game_duration_minutes,
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score;
                """), game_data)
            inserted_games += 1
        except Exception as db_err:
            print(f"Database write failure for Game {game_pk}: {db_err}")

    print(f"Game Feed Complete: Successfully committed {inserted_games} games with full boxscore data.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
