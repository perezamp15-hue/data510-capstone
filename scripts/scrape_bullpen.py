import sys
from datetime import datetime, timedelta
import pandas as pd
from db_client import get_engine, fetch_api_json

def run(date_str=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    sched_data = fetch_api_json(sched_url)
    
    bullpen_data = []
    for date_obj in sched_data.get("dates", []):
        for g in date_obj.get("games", []):
            game_pk = g.get("gamePk")
            box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
            try:
                box_data = fetch_api_json(box_url)
                for side in ['home', 'away']:
                    pitchers = box_data['teams'][side].get('pitchers', [])
                    if len(pitchers) > 1:
                        # Exclude the starting pitcher [0]
                        for r_id in pitchers[1:]:
                            p_info = box_data['teams'][side]['players'][f"ID{r_id}"]['stats'].get('pitching', {})
                            bullpen_data.append({
                                "pitcher_id": r_id,
                                "game_pk": game_pk,
                                "innings": p_info.get("inningsPitched"),
                                "pitches": p_info.get("numberOfPitches"),
                                "batters_faced": p_info.get("battersFaced"),
                                "days_rest": None # Engineered down-stream
                            })
            except Exception as e:
                print(f"Could not query bullpen for {game_pk}: {e}")

    if bullpen_data:
        pd.DataFrame(bullpen_data).to_sql('bullpen_appearances', get_engine(), if_exists='append', index=False)
