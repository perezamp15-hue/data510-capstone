"""
Data Science Studio Scrum (DS3) - Robust Ingestion Engine
Description: Seeds, harvests, and populates cloud relational staging zones with error safety.
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
    print("\n[STEP 1] Seeding Stadium Registries...")
    stadium_data = [
        {"stadium_id": "yankees", "name": "Yankee Stadium", "team": "New York Yankees", "latitude": 40.8296, "longitude": -73.9262, "altitude_ft": 54},
        {"stadium_id": "mets", "name": "Citi Field", "team": "New York Mets", "latitude": 40.7571, "longitude": -73.8458, "altitude_ft": 15},
        {"stadium_id": "dodgers", "name": "Dodger Stadium", "team": "Los Angeles Dodgers", "latitude": 34.0739, "longitude": -118.2400, "altitude_ft": 502}
    ]
    df = pd.DataFrame(stadium_data)
    df.to_sql("stg_stadiums", con=engine, if_exists="replace", index=False)
    print(f" Loaded {len(df)} ballparks into stg_stadiums.")

def ingest_schedules_and_statcast(engine):
    print("\n[STEP 2] Extracting Schedules & Telemetry...")
    
    # Using reliable mid-season dates to guarantee the scraper finds active game records
    seasons = [
        {"start": "2024-06-10", "end": "2024-06-12"},
        {"start": "2025-06-09", "end": "2025-06-11"}
    ]
    
    integrated_games = []
    for yr in [2024, 2025]:
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
            print(f"⚠️ Schedule fetch failed for season {yr}: {e}")

    if not integrated_games:
        print("❌ CRITICAL: No games found in schedule extraction. Aborting run.")
        return []

    df_games = pd.DataFrame(integrated_games)
    df_games.to_sql("stg_schedules", con=engine, if_exists="replace", index=False)
    print(f" Saved {len(df_games)} rows to stg_schedules table.")

    # 2. Harvest Statcast Telemetry
    print("Gathering Statcast pitch telemetry...")
    for chunk in seasons:
        try:
            df_sc = statcast(start_dt=chunk["start"], end_dt=chunk["end"])
            if df_sc is not None and not df_sc.empty:
                cols = ['game_date', 'batter', 'pitcher', 'events', 'description', 'home_team', 'away_team']
                df_fil = df_sc[df_sc['events'].notna()][cols]
                df_fil.to_sql("stg_statcast_pitches", con=engine, if_exists="append", index=False)
                print(f" Appended {len(df_fil)} pitch records for {chunk['start']}.")
            else:
                print(f"⚠️ Statcast returned no records for range: {chunk['start']}")
        except Exception as e:
            print(f"⚠️ Statcast endpoint error: {e}")

    # Return the 15 most recent valid game keys to process
    return [g["game_pk"] for g in integrated_games if g.get("game_pk")][-15:]

def ingest_boxscore_performance_logs(engine, target_pks):
    print(f"\n[STEP 3] Fetching boxscores for {len(target_pks)} active game keys...")
    if not target_pks:
        print("❌ Skipping Boxscores: Target game list is empty.")
        return

    flattened_logs = []
    for pk in target_pks:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                teams_data = resp.json().get("teams", {})
                flattened_logs.append({"game_pk": pk, "log_data": json.dumps(teams_data)})
        except Exception as e:
            print(f"⚠️ Boxscore fetch skipped for game {pk}: {e}")
        time.sleep(0.1)
        
    if flattened_logs:
        pd.DataFrame(flattened_logs).to_sql("stg_game_logs", con=engine, if_exists="replace", index=False)
        print(f" Saved {len(flattened_logs)} boxscores to stg_game_logs.")
    else:
        print("❌ No boxscore profiles could be gathered.")

if __name__ == "__main__":
    db_engine = get_database_engine()
    seed_stadium_registry(db_engine)
    active_pks = ingest_schedules_and_statcast(db_engine)
    ingest_boxscore_performance_logs(db_engine, active_pks)
    print("\n✅ INGESTION PIPELINE PASS RUN COMPLETE.")
