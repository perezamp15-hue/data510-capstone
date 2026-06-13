"""
Data Science Studio Scrum (DS3) - Railway Database Sync Module
Description: Automatically streams multi-structured raw payloads (CSV & JSON) 
             directly into Beekeeper-managed staging tables on Railway.
"""
import os
import sys
import json
import pandas as pd
from sqlalchemy import create_engine

def upload_processed_data_to_railway():
    print("==================================================================")
    print("EXECUTING INGESTION STREAM TO CLOUD STAGING TABLES")
    print("==================================================================")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing. Skipping database streaming phase.")
        return
        
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)

    # 1. Stream Stadium Matrix -> stg_stadiums
    stadium_path = "data/raw/stadium_registry.csv"
    if os.path.exists(stadium_path):
        print("Streaming stadium data -> stg_stadiums...")
        df_stadiums = pd.read_csv(stadium_path)
        df_stadiums.to_sql("stg_stadiums", con=engine, if_exists="replace", index=False)
    else:
        print(f"Warning: {stadium_path} not found.")

    # 2. Stream Statcast Pitch Matrix -> stg_statcast_pitches
    pitches_path = "data/raw/statcast_pitches_raw.csv"
    if os.path.exists(pitches_path):
        print("Streaming pitch telemetry data -> stg_statcast_pitches...")
        df_pitches = pd.read_csv(pitches_path)
        # Use append here to preserve any pre-existing historical telemetry chunks
        df_pitches.to_sql("stg_statcast_pitches", con=engine, if_exists="append", index=False)
    else:
        print(f"Warning: {pitches_path} not found.")

    # 3. Stream Schedules & Lineups Matrix -> stg_schedules
    schedules_path = "data/raw/mlb_games_with_players_raw.json"
    if os.path.exists(schedules_path):
        print("Streaming schedule matrices -> stg_schedules...")
        with open(schedules_path, "r") as f:
            sched_data = json.load(f)
        
        # Flatten dictionary elements to cleanly fit tabular row layout
        flattened_sched = []
        for match in sched_data:
            flattened_sched.append({
                "game_pk": match["game_pk"],
                "game_date": match["game_date"],
                "home_team": match["home_team"],
                "away_team": match["away_team"],
                # Serialize the inner lineup array block into a JSON string for JSONB mapping
                "starting_lineups": json.dumps(match["starting_lineups"])
            })
        if flattened_sched:
            df_sched = pd.DataFrame(flattened_sched)
            df_sched.to_sql("stg_schedules", con=engine, if_exists="replace", index=False)
    else:
        print(f"Warning: {schedules_path} not found.")

    # 4. Stream Detailed Player Game Logs -> stg_game_logs
    logs_path = "data/raw/detailed_game_logs.json"
    if os.path.exists(logs_path):
        print("Streaming role-separated player data logs -> stg_game_logs...")
        with open(logs_path, "r") as f:
            logs_data = json.load(f)
            
        flattened_logs = [{"game_pk": pk, "log_data": json.dumps(payload)} for pk, payload in logs_data.items()]
        if flattened_logs:
            df_logs = pd.DataFrame(flattened_logs)
            df_logs.to_sql("stg_game_logs", con=engine, if_exists="replace", index=False)
    else:
        print(f"Warning: {logs_path} not found.")

    print("\n-> SUCCESS: Database staging layer sync complete. Tables are live in Beekeeper!")
    print("==================================================================")

if __name__ == "__main__":
    upload_processed_data_to_railway()
