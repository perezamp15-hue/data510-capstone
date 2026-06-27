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
            
        home_node = game.get('teams', {}).get('home', {})
        away_node = game.get('teams', {}).get('away', {})
        
        game_dict = {
            "game_pk": int(pk),
            "game_date": target_date,
            "game_type": game.get('gameType', 'R'),
            "season": int(game.get('season', 2026)),
            "home_team_id": int(home_node.get('team', {}).get('id')),
            "away_team_id": int(away_node.get('team', {}).get('id')),
            "park_id": int(game.get('venue', {}).get('id')),
            "home_score": int(home_node.get('score', 0)) if home_node.get('score') is not None else None,
            "away_score": int(away_node.get('score', 0)) if away_node.get('score') is not None else None
        }

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, game_type, season, home_team_id, 
                        away_team_id, park_id, home_score, away_score
                    )
                    VALUES (
                        :game_pk, :game_date, :game_type, :season, :home_team_id, 
                        :away_team_id, :park_id, :home_score, :away_score
                    )
                    ON CONFLICT (game_pk) DO UPDATE SET
                        home_score = EXCLUDED.home_score,
                        away_score = EXCLUDED.away_score;
                """), game_dict)
            games_saved += 1
        except Exception as e:
            print(f"Failed to write boxscore index for game {pk}: {e}")
            continue

    print(f"Game Feed Complete: Successfully saved {games_saved} games.")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
