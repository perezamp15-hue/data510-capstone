"""
Data Science Studio Scrum (DS3) - Ingestion Engine
Description: Seeds, harvests, and populates cloud relational staging zones.
"""
import os
import sys
import json
import time
import requests
import pandas as pd
from sqlalchemy import create_engine, text
from pybaseball import statcast

def get_database_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ CRITICAL ERROR: DATABASE_URL environment variable is blank.")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)

def seed_stadium_registry(engine):
    print("\n[STEP 1] Compiling and Seeding Stadium Registries...")
    stadium_data = [
        {"stadium_id": "yankees", "name": "Yankee Stadium", "team": "New York Yankees", "latitude": 40.8296, "longitude": -73.9262, "altitude_ft": 54},
        {"stadium_id": "mets", "name": "Citi Field", "team": "New York Mets", "latitude": 40.7571, "longitude": -73.8458, "altitude_ft": 15},
        {"stadium_id": "dodgers", "name": "Dodger Stadium", "team": "Los Angeles Dodgers", "latitude": 34.0739, "longitude": -118.2400, "altitude_ft": 502},
        {"stadium_id": "red_sox", "name": "Fenway Park", "team": "Boston Red Sox", "latitude": 42.3467, "longitude": -71.0972, "altitude_ft": 20},
        {"stadium_id": "cubs", "name": "Wrigley Field", "team": "Chicago Cubs", "latitude": 41.9484, "longitude": -87.6553, "altitude_ft": 600}
    ]
    df = pd.DataFrame(stadium_data)
    df.to_sql("stg_stadiums", con=engine, if_exists="replace", index=False)
    print(f" Loaded {len(df)} base ballparks into 'stg_stadiums'.")
    return stadium_data

def ingest_schedules_and_statcast(engine):
    print("\n[STEP 2] Extracting Multi-Season Schedules & Telemetry...")
    seasons = [
        {"start": "2024-03-28", "end": "2024-03-30"},
        {"start": "2025-03-27", "end": "2025-03-29"},
        {"start": "2026-03-26", "end": "2026-03-28"}
    ]
    
    # 1. Harvest Schedules
    integrated_games = []
    for yr in [2024, 2025, 2026]:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={yr}&gameType=R"
        try:
            res = requests.get(url, timeout=12)
            if res.status_code == 200:
                for d_node in res.json().get("dates", []):
                    for gm in d_node.get("games", []):
                        integrated_games.append({
                            "game_pk": gm.get("gamePk"),
                            "game_date": gm.get("gameDate").split("T")[0],
                            "home_team": gm.get("teams", {}).get("home", {}).get("team", {}).get("name"),
                            "away_team": gm.get("teams", {}).get("away", {}).get("team", {}).get("name")
                        })
        except Exception as e:
            print(f"Schedule warning for {yr}: {e}")

    if integrated_games:
        pd.DataFrame(integrated_games).to_sql("stg_schedules", con=engine, if_exists="replace", index=False)
        print(f" Loaded {len(integrated_games)} records into 'stg_schedules'.")

    # 2. Harvest Statcast Telemetry Chunks
    print("Gathering pybaseball Statcast metrics...")
    first_block = True
    for chunk in seasons:
        try:
            df_sc = statcast(start_dt=chunk["start"], end_dt=chunk["end"])
            if df_sc is not None and not df_sc.empty:
                cols = ['game_date', 'batter', 'pitcher', 'events', 'description', 'home_team', 'away_team']
                df_fil = df_sc[df_sc['events'].notna()][cols]
                mode_option = "replace" if first_block else "append"
                df_fil.to_sql("stg_statcast_pitches", con=engine, if_exists=mode_option, index=False)
                print(f" Appended {len(df_fil)} events for date block {chunk['start']}.")
                first_block = False
        except Exception as e:
            print(f"Statcast collection alert for {chunk['start']}: {e}")

    return execution_slice_pks(integrated_games)

def execution_slice_pks(games_list):
    return [g["game_pk"] for g in games_list if g.get("game_pk")][-30:]

def ingest_boxscore_performance_logs(engine, target_pks):
    print("\n[STEP 3] Running Ingestion on Player Performance Boxscores...")
    flattened_logs = []
    
    for idx, pk in enumerate(target_pks, 1):
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                teams_data = resp.json().get("teams", {})
                flattened_logs.append({"game_pk": pk, "log_data": json.dumps(teams_data)})
        except Exception as e:
            print(f"Skipping match key {pk}: {e}")
        time.sleep(0.05)
        
    if flattened_logs:
        pd.DataFrame(flattened_logs).to_sql("stg_game_logs", con=engine, if_exists="replace", index=False)
        print(f" Populated {len(flattened_logs)} boxscores into 'stg_game_logs'.")

if __name__ == "__main__":
    db_engine = get_database_engine()
    seed_stadium_registry(db_engine)
    active_pks = ingest_schedules_and_statcast(db_engine)
    ingest_boxscore_performance_logs(db_engine, active_pks)
    print("\n✅ PHASE 1 COMPLETE: Raw logs stored in staging layers.")
