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

    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}&hydrate=linescore,boxscore,decisions"
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

        # Core keys
        game_type = g.get('gameType', 'R') 
        api_venue_id = g.get('venue', {}).get('id')
        
        home_node = g.get('teams', {}).get('home', {})
        away_node = g.get('teams', {}).get('away', {})
        
        home_team_id = home_node.get('team', {}).get('id')
        away_team_id = away_node.get('team', {}).get('id')

        # Pitcher Decisions
        decisions = g.get('decisions', {})
        winner_id = decisions.get('winner', {}).get('id')
        loser_id = decisions.get('loser', {}).get('id')
        save_id = decisions.get('save', {}).get('id')

        day_night_type = g.get('dayNight')

        # SPLIT TIME FROM DATE AREA
        raw_game_date = g.get('gameDate') # e.g., "2026-06-22T22:10:00Z"
        parsed_time = None
        if raw_game_date and 'T' in raw_game_date:
            try:
                # Splits at 'T' -> takes the second part -> removes the timezone 'Z'
                parsed_time = raw_game_date.split('T')[1].replace('Z', '')
            except Exception:
                parsed_time = None

        # Parse Info array (Attendance and Duration)
        game_info = g.get('boxscore', {}).get('info', [])
        attendance = None
        duration_mins = None
        
        for info in game_info:
            label = info.get('label', '')
            value = info.get('value', '')
            if 'Attendance' in label or 'Att' in label:
                try: 
                    clean_val = ''.join(c for c in value if c.isdigit())
                    attendance = int(clean_val)
                except: pass
            if label == 'T' or 'Duration' in label:
                try:
                    parts = value.split(':')
                    duration_mins = int(parts[0]) * 60 + int(parts[1])
                except: pass

        # Fallback duration check
        if not duration_mins and g.get('gameTimeMinutes'):
            try: duration_mins = int(g.get('gameTimeMinutes'))
            except: pass

        # Scores
        linescore = g.get('linescore', {})
        home_score = linescore.get('teams', {}).get('home', {}).get('runs')
        away_score = linescore.get('teams', {}).get('away', {}).get('runs')

        game_data = {
            "game_pk": int(game_pk),
            "game_date": target_date,
            "season": season_year,
            "game_type": game_type,
            "scheduled_start": parsed_time, # Corrected parameter mapping
            "park_id": int(api_venue_id) if api_venue_id else None, 
            "home_team_id": int(home_team_id) if home_team_id else None,
            "away_team_id": int(away_team_id) if away_team_id else None,
            "day_night_type": day_night_type,
            "attendance": attendance,
            "game_duration_minutes": duration_mins,
            "home_score": home_score,
            "away_score": away_score,
            "winning_pitcher_id": int(winner_id) if winner_id else None,
            "losing_pitcher_id": int(loser_id) if loser_id else None,
            "save_pitcher_id": int(save_id) if save_id else None
        }

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, season, game_type, scheduled_start, park_id, 
                        home_team_id, away_team_id, day_night_type, 
                        attendance, game_duration_minutes, home_score, away_score,
                        winning_pitcher_id, losing_pitcher_id, save_pitcher_id
                    )
                    VALUES (
                        :game_pk, :game_date, :season, :game_type, :scheduled_start, :park_id, 
                        :home_team_id, :away_team_id, :day_night_type, 
                        :attendance, :game_duration_minutes, :home_score, :away_score,
                        :winning_pitcher_id, :losing_pitcher_id, :save_pitcher_id
                    )
                    ON CONFLICT (game_pk) DO UPDATE SET
                        park_id = EXCLUDED.park_id,
                        game_date = EXCLUDED.game_date,
                        season = EXCLUDED.season,
                        game_type = EXCLUDED.game_type,
                        scheduled_start = EXCLUDED.scheduled_start,
                        day_night_type = EXCLUDED.day_night_type,
                        attendance = EXCLUDED.attendance,
                        game_duration_minutes = EXCLUDED.game_duration_minutes,
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        winning_pitcher_id = EXCLUDED.winning_pitcher_id,
                        losing_pitcher_id = EXCLUDED.losing_pitcher_id,
                        save_pitcher_id = EXCLUDED.save_pitcher_id;
                """), game_data)
            inserted_games += 1
        except Exception as db_err:
            print(f"Database write failure for Game {game_pk}: {db_err}")

    print(f"Game Feed Complete: Successfully saved {inserted_games} games with exact scheduled_start profiles.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
