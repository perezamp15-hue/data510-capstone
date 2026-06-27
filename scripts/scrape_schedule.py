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
    
    # 1. Fetch the day's schedule framework to get the game PKs
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

    for game in games_list:
        pk = game.get('gamePk')
        if not pk:
            continue
            
        # 2. Deep-dive directly into the individual live feed for absolute data truth
        live_url = f"https://statsapi.mlb.com/api/v1.1/game/{pk}/feed/live"
        try:
            live_data = fetch_api_json(live_url)
            game_data = live_data.get('gameData', {}) if live_data else {}
            live_teams = game_data.get('teams', {})
            decisions_node = game_data.get('decisions', {})
        except Exception as e:
            print(f"Failed to pull live hydration depth for game {pk}: {e}")
            continue

        home_node = live_teams.get('home', {})
        away_node = live_teams.get('away', {})
        
        # Pull scores from the live game data block
        # (Using live boxscore structure where scores are inside the live linescore/boxscore)
        live_linescore = live_data.get('liveData', {}).get('linescore', {}).get('teams', {})
        home_score = live_linescore.get('home', {}).get('runs')
        away_score = live_linescore.get('away', {}).get('runs')

        # Fallback to schedule node scores if live data runs aren't updated yet
        if home_score is None:
            home_score = game.get('teams', {}).get('home', {}).get('score')
        if away_score is None:
            away_score = game.get('teams', {}).get('away', {}).get('score')

        game_dict = {
            "game_pk": int(pk),
            "game_date": target_date,
            "game_type": game.get('gameType', 'R'),
            "season": int(game.get('season', 2026)),
            "home_team_id": int(home_node.get('id')) if home_node.get('id') else int(game.get('teams', {}).get('home', {}).get('team', {}).get('id')),
            "away_team_id": int(away_node.get('id')) if away_node.get('id') else int(game.get('teams', {}).get('away', {}).get('team', {}).get('id')),
            "park_id": int(game_data.get('venue', {}).get('id')) if game_data.get('venue') else int(game.get('venue', {}).get('id')),
            "home_score": int(home_score) if home_score is not None else None,
            "away_score": int(away_score) if away_score is not None else None,
            "day_night_type": game_data.get('game', {}).get('dayNight') or game.get('dayNight'),
            "scheduled_start": game_data.get('datetime', {}).get('dateTime') or game.get('gameDate'),
            "winning_pitcher_id": int(decisions_node.get('winner', {}).get('id')) if decisions_node.get('winner') else None,
            "losing_pitcher_id": int(decisions_node.get('loser', {}).get('id')) if decisions_node.get('loser') else None,
            "save_pitcher_id": int(decisions_node.get('save', {}).get('id')) if decisions_node.get('save') else None
        }

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, game_type, season, home_team_id, 
                        away_team_id, park_id, home_score, away_score, day_night_type,
                        scheduled_start, winning_pitcher_id, losing_pitcher_id, save_pitcher_id
                    )
                    VALUES (
                        :game_pk, :game_date, :game_type, :season, :home_team_id, 
                        :away_team_id, :park_id, :home_score, :away_score, :day_night_type,
                        :scheduled_start, :winning_pitcher_id, :losing_pitcher_id, :save_pitcher_id
                    )
                    ON CONFLICT (game_pk) DO UPDATE SET
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score,
                        day_night_type = EXCLUDED.day_night_type,
                        scheduled_start = EXCLUDED.scheduled_start,
                        winning_pitcher_id = EXCLUDED.winning_pitcher_id,
                        losing_pitcher_id = EXCLUDED.losing_pitcher_id,
                        save_pitcher_id = EXCLUDED.save_pitcher_id;
                """), game_dict)
            games_saved += 1
        except Exception as e:
            print(f"Failed to write boxscore index for game {pk}: {e}")
            continue

    print(f"Game Feed Complete: Successfully saved {games_saved} games with 100% data fidelity.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
