"""
Data Science Studio Scrum (DS3) - Milestone M2 Data Processing Engine
Description: Extracts raw telemetry from cloud staging tables, maps biographical
             player frameworks, and builds the core feature layer.
"""
import os
import sys
import time
import requests
import pandas as pd
from sqlalchemy import create_engine

def clean_and_map_player_ids():
    print("==================================================================")
    print("STARTING DATA PROCESSING ENGINE: FEATURE GENERATION")
    print("==================================================================")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing. Skipping processing phase.")
        return
        
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(database_url)
    
    # 1. Pull Raw Telemetry directly from the Database Staging Layer
    print("Fetching raw records from stg_statcast_pitches...")
    try:
        df_raw = pd.read_sql_table("stg_statcast_pitches", con=engine)
    except Exception as e:
        print(f"Database Error: Could not read staging data. {e}")
        sys.exit(1)
        
    if df_raw.empty:
        print("Staging table is empty. Run ingestion scripts first.")
        return

    # Extract all unique player IDs present in the current data chunk
    all_unique_ids = list(set(df_raw['batter'].dropna().unique()).union(set(df_raw['pitcher'].dropna().unique())))
    print(f"Identified {len(all_unique_ids)} unique player profiles to map.")
    
    player_registry = []
    
    # 2. Gather biographical features from MLB StatsAPI
    # Note: For production, we remove the loop slice so ALL players are mapped correctly
    for idx, player_id in enumerate(all_unique_ids, 1):
        if idx % 20 == 0:
            print(f"Mapped {idx}/{len(all_unique_ids)} players...")
            
        url = f"https://statsapi.mlb.com/api/v1/people/{int(player_id)}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                person = res.json().get("people", [])[0]
                player_registry.append({
                    "player_id": int(player_id),
                    "clean_full_name": person.get("fullName"),
                    "primary_position": person.get("primaryPosition", {}).get("abbreviation"),
                    "bat_side": person.get("batSide", {}).get("code"),
                    "pitch_hand": person.get("pitchHand", {}).get("code")
                })
        except Exception:
            pass
        time.sleep(0.02)  # Generous safety delay to honor API thresholds
        
    df_reg = pd.DataFrame(player_registry)
    
    if df_reg.empty:
        print("Critical Error: Player biographical registry could not be constructed.")
        return

    print("\nMerging dimensions and executing structural transformations...")
    
    # 3. Join biographical features onto raw at-bats
    # Map Batter Features
    df_clean = df_raw.merge(df_reg, left_on='batter', right_on='player_id', how='left')
    df_clean = df_clean.rename(columns={
        "batter": "batter_id",
        "clean_full_name": "batter_name",
        "bat_side": "batter_stance",
        "primary_position": "batter_position"
    }).drop(columns=['player_id', 'pitch_hand'])
    
    # Map Pitcher Features
    df_clean = df_clean.merge(df_reg, left_on='pitcher', right_on='player_id', how='left')
    df_clean = df_clean.rename(columns={
        "pitcher": "pitcher_id",
        "clean_full_name": "pitcher_name",
        "pitch_hand": "pitcher_throw_hand"
    }).drop(columns=['player_id', 'bat_side', 'primary_position'])
    
    # Clean up any residual dataframe index columns before loading
    if 'id' in df_clean.columns:
        df_clean = df_clean.drop(columns=['id'])

    # 4. Stream Cleaned Features into the Core Production Table
    print("Pouring final transformed features into core_at_bats...")
    try:
        df_clean.to_sql("core_at_bats", con=engine, if_exists="replace", index=False)
        print("\n-> SUCCESS: Core feature layer generated and live in Beekeeper!")
        print("==================================================================")
    except Exception as e:
        print(f"Database Write Error: {e}")

if __name__ == "__main__":
    clean_and_map_player_ids()
