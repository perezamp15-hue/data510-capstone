import sys
import datetime
import requests
import pandas as pd
import numpy as np
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(season=2026):
    print(f"Compiling framework calendar structures for {season}...")
    engine = get_engine()
    
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&season={season}&hydrate=decisions"
    try:
        schedule_data = fetch_api_json(url)
        dates_node = schedule_data.get('dates', [])
    except Exception as e:
        print(f"CRITICAL: Master calendar sync aborted: {e}")
        return

    parsed_games = []
    
    # Define valid MLB championship game types explicitly
    VALID_GAME_TYPES = {'R', 'F', 'D', 'L', 'W', 'A'}

    for date_block in dates_node:
        g_date = date_block.get('date')
        games_list = date_block.get('games', [])
        
        for game in games_list:
            pk = game.get('gamePk')
            g_type = game.get('gameType', 'R')
            
            # FILTER IN PYTHON: Skip non-championship/spring/exhibition games immediately
            if not pk or g_type not in VALID_GAME_TYPES:
                continue
                
            home_node = game.get('teams', {}).get('home', {})
            away_node = game.get('teams', {}).get('away', {})
            decisions_node = game.get('decisions', {})
            
            def safe_float_or_int(val):
                if val is None or str(val).strip() == "":
                    return None
                try:
                    return int(float(val))
                except:
                    return None

            parsed_games.append({
                "game_pk": safe_float_or_int(pk),
                "game_date": g_date,
                "game_type": g_type,
                "season": safe_float_or_int(season),
                "home_team_id": safe_float_or_int(home_node.get('team', {}).get('id')),
                "away_team_id": safe_float_or_int(away_node.get('team', {}).get('id')),
                "park_id": safe_float_or_int(game.get('venue', {}).get('id')),
                "home_score": safe_float_or_int(home_node.get('score')),
                "away_score": safe_float_or_int(away_node.get('score')),
                "day_night_type": game.get('dayNight'),
                "scheduled_start": game.get('gameDate'),
                "winning_pitcher_id": safe_float_or_int(decisions_node.get('winner', {}).get('id')),
                "losing_pitcher_id": safe_float_or_int(decisions_node.get('loser', {}).get('id')),
                "save_pitcher_id": safe_float_or_int(decisions_node.get('save', {}).get('id'))
            })

    df = pd.DataFrame(parsed_games)
    if df.empty:
        print(f"No calendar entries found for season {season}.")
        return

    # 1. Force columns to Pandas' native nullable integer type to avoid .0 float conversion
    int_cols = [
        "game_pk", "season", "home_team_id", "away_team_id", "park_id", 
        "home_score", "away_score", "winning_pitcher_id", "losing_pitcher_id", "save_pitcher_id"
    ]
    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')

    # 2. De-duplicate primary game keys to satisfy Postgres ON CONFLICT constraints
    df = df.drop_duplicates(subset=['game_pk'])

    try:
        print(f"Bulk loading {len(df)} games to temporary staging table...")
        df.to_sql("tmp_schedule_staging", con=engine, if_exists="replace", index=False)

        print("Merging staging table into master games directory...")
        with engine.begin() as conn:
            # BACKUP PROTECTION: Filter by existing parks to avoid FK errors from any mixed-label API records
            conn.execute(text("""
                INSERT INTO games (
                    game_pk, game_date, game_type, season, home_team_id, 
                    away_team_id, park_id, home_score, away_score, day_night_type,
                    scheduled_start, winning_pitcher_id, losing_pitcher_id, save_pitcher_id
                )
                SELECT 
                    CAST(s.game_pk AS INTEGER), 
                    CAST(s.game_date AS DATE), 
                    s.game_type, 
                    CAST(s.season AS INTEGER), 
                    CAST(s.home_team_id AS INTEGER), 
                    CAST(s.away_team_id AS INTEGER), 
                    CAST(s.park_id AS INTEGER), 
                    CAST(s.home_score AS INTEGER), 
                    CAST(s.away_score AS INTEGER), 
                    s.day_night_type,
                    CAST(s.scheduled_start AS TIMESTAMPTZ),
                    CASE WHEN p_win.player_id IS NOT NULL THEN CAST(s.winning_pitcher_id AS INTEGER) ELSE NULL END,
                    CASE WHEN p_lose.player_id IS NOT NULL THEN CAST(s.losing_pitcher_id AS INTEGER) ELSE NULL END,
                    CASE WHEN p_save.player_id IS NOT NULL THEN CAST(s.save_pitcher_id AS INTEGER) ELSE NULL END
                FROM tmp_schedule_staging s
                INNER JOIN parks p ON CAST(s.park_id AS INTEGER) = p.park_id
                LEFT JOIN players p_win ON CAST(s.winning_pitcher_id AS INTEGER) = p_win.player_id
                LEFT JOIN players p_lose ON CAST(s.losing_pitcher_id AS INTEGER) = p_lose.player_id
                LEFT JOIN players p_save ON CAST(s.save_pitcher_id AS INTEGER) = p_save.player_id
                WHERE s.game_type IN ('R', 'F', 'D', 'L', 'W', 'A')
                ON CONFLICT (game_pk) DO UPDATE SET
                    home_score = EXCLUDED.home_score,
                    away_score = EXCLUDED.away_score,
                    day_night_type = EXCLUDED.day_night_type,
                    scheduled_start = EXCLUDED.scheduled_start,
                    winning_pitcher_id = EXCLUDED.winning_pitcher_id,
                    losing_pitcher_id = EXCLUDED.losing_pitcher_id,
                    save_pitcher_id = EXCLUDED.save_pitcher_id;
            """))
            
            conn.execute(text("DROP TABLE IF EXISTS tmp_schedule_staging;"))
            
        print(f"Master Schedule Sync finished: Successfully indexed official games.")
        
    except Exception as e:
        print(f"Schedule Sync Error: {e}")

if __name__ == "__main__":
    passed_season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    run(season=passed_season)
