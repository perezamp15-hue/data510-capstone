import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(season=2026):
    print(f"Compiling framework calendar structures for {season}...")
    engine = get_engine()
    
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&season={season}"
    try:
        schedule_data = fetch_api_json(url)
        dates_node = schedule_data.get('dates', [])
    except Exception as e:
        print(f"CRITICAL: Master calendar sync aborted: {e}")
        return

    calendar_count = 0
    for date_block in dates_node:
        g_date = date_block.get('date')
        games_list = date_block.get('games', [])
        
        for game in games_list:
            pk = game.get('gamePk')
            if not pk:
                continue
                
            home_node = game.get('teams', {}).get('home', {})
            away_node = game.get('teams', {}).get('away', {})
            
            sched_dict = {
                "game_pk": int(pk),
                "game_date": g_date,
                "game_type": game.get('gameType', 'R'),
                "season": int(season),
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
                    """), sched_dict)
                calendar_count += 1
            except Exception:
                continue

    print(f"Master Schedule Sync finished: Indexed {calendar_count} games into structural framework.")

if __name__ == "__main__":
    passed_season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    run(passed_season)
