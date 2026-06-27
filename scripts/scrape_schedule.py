import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(season=2026):
    print(f"Compiling framework calendar structures for {season}...")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}"
    try:
        data = fetch_api_json(url)
        dates = data.get('dates', [])
        parsed = []
        engine = get_engine()
        valid_games = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        for d in dates:
            for g in d.get('games', []):
                g_pk = int(g.get('gamePk'))
                if g_pk not in valid_games: continue
                parsed.append({"game_pk": g_pk, "season_year": season, "game_type": g.get('gameType', 'R')})
        df = pd.DataFrame(parsed).drop_duplicates(subset=['game_pk'])
        if df.empty: return
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO team_schedules (game_pk, season_year, game_type) VALUES (:game_pk, :season_year, :game_type)
                    ON CONFLICT (game_pk) DO UPDATE SET season_year = EXCLUDED.season_year, game_type = EXCLUDED.game_type;
                """), row.to_dict())
    except Exception as e: print(f"Schedule Error: {e}")

if __name__ == "__main__": run()
