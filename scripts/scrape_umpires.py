import sys
from datetime import datetime, timedelta
import pandas as pd
from scripts.db_client import get_engine, fetch_api_json

def run(date_str=None):
    if not date_str:
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
    sched_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    sched_data = fetch_api_json(sched_url)
    
    umpire_records = []
    for date_obj in sched_data.get("dates", []):
        for g in date_obj.get("games", []):
            game_pk = g.get("gamePk")
            box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
            try:
                box_data = fetch_api_json(box_url)
                officials = box_data.get("officials", [])
                ump_dict = {"game_pk": game_pk, "hp_umpire": None, "ump_1b": None, "ump_2b": None, "ump_3b": None}
                
                for off in officials:
                    role = off.get("officialType")
                    name = off.get("official", {}).get("fullName")
                    if role == "Home Plate": ump_dict["hp_umpire"] = name
                    elif role == "First Base": ump_dict["ump_1b"] = name
                    elif role == "Second Base": ump_dict["ump_2b"] = name
                    elif role == "Third Base": ump_dict["ump_3b"] = name
                    
                umpire_records.append(ump_dict)
            except Exception as e:
                print(f"Umpire extraction issue on {game_pk}: {e}")

    if umpire_records:
        pd.DataFrame(umpire_records).to_sql('game_umpires', get_engine(), if_exists='append', index=False)
