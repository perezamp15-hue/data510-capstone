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
    print(f"Ingesting main boxscore feed matrices for {target_date}...")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={target_date}"
    try:
        schedule_data = fetch_api_json(url)
        dates = schedule_data.get('dates', [])
        if not dates: return
        engine = get_engine()
        valid_parks = pd.read_sql("SELECT park_id FROM parks", con=engine)['park_id'].tolist()
        valid_players = pd.read_sql("SELECT player_id FROM players", con=engine)['player_id'].tolist()
        for date_node in dates:
            for game_summary in date_node.get('games', []):
                game_pk = int(game_summary.get('gamePk'))
                feed_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
                try: game_feed = fetch_api_json(feed_url)
                except Exception: continue
                game_data = game_feed.get('gameData', {})
                live_data = game_feed.get('liveData', {})
                linescore = live_data.get('linescore', {})
                boxscore = live_data.get('boxscore', {})
                v_id = game_data.get('venue', {}).get('id')
                park_id = int(v_id) if v_id and int(v_id) in valid_parks else None
                wp_id = game_data.get('gameInfo', {}).get('winningPitcher', {}).get('id')
                lp_id = game_data.get('gameInfo', {}).get('losingPitcher', {}).get('id')
                sp_id = game_data.get('gameInfo', {}).get('savePitcher', {}).get('id')
                winning_pitcher = int(wp_id) if wp_id and int(wp_id) in valid_players else None
                losing_pitcher = int(lp_id) if lp_id and int(lp_id) in valid_players else None
                save_pitcher = int(sp_id) if sp_id and int(sp_id) in valid_players else None
                home_id = int(game_data.get('teams', {}).get('home', {}).get('id'))
                away_id = int(game_data.get('teams', {}).get('away', {}).get('id'))
                home_runs = linescore.get('teams', {}).get('home', {}).get('runs', 0)
                away_runs = linescore.get('teams', {}).get('away', {}).get('runs', 0)
                game_dict = {
                    "game_pk": game_pk, "game_date": target_date, "season": int(game_data.get('game', {}).get('season', 2026)),
                    "game_type": game_data.get('game', {}).get('type', 'R'), "is_doubleheader": game_data.get('game', {}).get('doubleHeader') == 'Y',
                    "day_night_type": game_data.get('gameInfo', {}).get('dayNight'), "scheduled_start": game_data.get('datetime', {}).get('dateTime'),
                    "park_id": park_id, "home_team_id": home_id, "away_team_id": away_id, "home_score": home_runs, "away_score": away_runs,
                    "attendance": game_data.get('gameInfo', {}).get('attendance'), "game_duration_minutes": game_data.get('gameInfo', {}).get('gameDurationMinutes'),
                    "winning_pitcher_id": winning_pitcher, "losing_pitcher_id": losing_pitcher, "save_pitcher_id": save_pitcher
                }
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO games (game_pk, game_date, season, game_type, is_doubleheader, day_night_type, scheduled_start, park_id, home_team_id, away_team_id, home_score, away_score, attendance, game_duration_minutes, winning_pitcher_id, losing_pitcher_id, save_pitcher_id)
                        VALUES (:game_pk, :game_date, :season, :game_type, :is_doubleheader, :day_night_type, :scheduled_start, :park_id, :home_team_id, :away_team_id, :home_score, :away_score, :attendance, :game_duration_minutes, :winning_pitcher_id, :losing_pitcher_id, :save_pitcher_id)
                        ON CONFLICT (game_pk) DO UPDATE SET home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score, attendance = EXCLUDED.attendance, game_duration_minutes = EXCLUDED.game_duration_minutes, winning_pitcher_id = EXCLUDED.winning_pitcher_id, losing_pitcher_id = EXCLUDED.losing_pitcher_id, save_pitcher_id = EXCLUDED.save_pitcher_id;
                    """), game_dict)
                home_hits = boxscore.get('teams', {}).get('home', {}).get('teamStats', {}).get('batting', {}).get('hits', 0)
                away_hits = boxscore.get('teams', {}).get('away', {}).get('teamStats', {}).get('batting', {}).get('hits', 0)
                home_errs = boxscore.get('teams', {}).get('home', {}).get('teamStats', {}).get('fielding', {}).get('errors', 0)
                away_errs = boxscore.get('teams', {}).get('away', {}).get('teamStats', {}).get('fielding', {}).get('errors', 0)
                team_records = [
                    {"game_pk": game_pk, "team_id": home_id, "is_home": True, "runs": home_runs, "hits": home_hits, "errors": home_errs, "game_result": 'W' if home_runs > away_runs else 'L'},
                    {"game_pk": game_pk, "team_id": away_id, "is_home": False, "runs": away_runs, "hits": away_hits, "errors": away_errs, "game_result": 'W' if away_runs > home_runs else 'L'}
                ]
                with engine.begin() as conn:
                    for tr in team_records:
                        conn.execute(text("""
                            INSERT INTO team_games (game_pk, team_id, is_home, runs, hits, errors, game_result)
                            VALUES (:game_pk, :team_id, :is_home, :runs, :hits, :errors, :game_result)
                            ON CONFLICT (game_pk, team_id) DO UPDATE SET runs = EXCLUDED.runs, hits = EXCLUDED.hits, errors = EXCLUDED.errors, game_result = EXCLUDED.game_result;
                        """), tr)
    except Exception as e: print(f"Game Feed Error: {e}")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
