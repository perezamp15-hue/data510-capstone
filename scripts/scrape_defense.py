import sys
from datetime import datetime, timedelta
import pandas as pd
from scripts.db_client import get_engine, fetch_api_json

def run(date_str=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    sched_data = fetch_api_json(sched_url)
    
    alignments = []
    for date_obj in sched_data.get("dates", []):
        for g in date_obj.get("games", []):
            game_pk = g.get("gamePk")
            live_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
            try:
                live_data = fetch_api_json(live_url)
                box_data = live_data.get("liveData", {}).get("boxscore", {}).get("teams", {})
                for side in ['home', 'away']:
                    for p_key, p_val in box_data.get(side, {}).get("players", {}).items():
                        if "jerseyNumber" in p_val:
                            alignments.append({
                                "game_pk": game_pk,
                                "player_id": p_val.get("person", {}).get("id"),
                                "team": side,
                                "position": p_val.get("position", {}).get("abbreviation")
                            })
            except Exception as e:
                print(f"Skipping defense check for {game_pk}: {e}")

    if alignments:
        pd.DataFrame(alignments).to_sql('defensive_alignments', get_engine(), if_exists='append', index=False)
