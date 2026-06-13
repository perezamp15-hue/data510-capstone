"""
Data Science Studio Scrum (DS3) - Milestone M2 Data Processing Engine
Author: Aaron Perez 
Description: Eliminates string variance by translating raw at-bat data keys into clean registries.
"""

import os
import time
import requests
import pandas as pd

def clean_and_map_player_ids():
    raw_path = "data/raw/statcast_pitches_raw.csv"
    processed_dir = "data/processed"
    os.makedirs(processed_dir, exist_ok=True)

    if not os.path.exists(raw_path):
        print("Aborting: Raw Statcast database tracking file not found.")
        return

    df_raw = pd.read_csv(raw_path)
    all_unique_ids = list(set(df_raw['batter'].unique()).union(set(df_raw['pitcher'].unique())))
    print(f"Extracted {len(all_unique_ids)} unique player numbers. Re-indexing clean names...")
    
    player_registry = []
    for count, player_id in enumerate(all_unique_ids, 1):
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                person = res.json().get("people", [])[0]
                player_registry.append({
                    "player_id": player_id, "clean_full_name": person.get("fullName"),
                    "primary_position": person.get("primaryPosition", {}).get("abbreviation"),
                    "bat_side": person.get("batSide", {}).get("code"),
                    "pitch_hand": person.get("pitchHand", {}).get("code")
                })
        except Exception:
            pass
        time.sleep(0.05)

    df_reg = pd.DataFrame(player_registry)
    df_reg.to_csv(f"{processed_dir}/player_registry.csv", index=False)
    
    # Execute relational merges to map clean features onto master dataframe rows
    df_clean = df_raw.merge(df_reg, left_on='batter', right_on='player_id', how='left').rename(columns={
        "clean_full_name": "batter_name", "bat_side": "batter_stance", "primary_position": "batter_position"
    }).drop(columns=['player_id', 'pitch_hand'])

    df_clean = df_clean.merge(df_reg, left_on='pitcher', right_on='player_id', how='left').rename(columns={
        "clean_full_name": "pitcher_name", "pitch_hand": "pitcher_throw_hand"
    }).drop(columns=['player_id', 'bat_side', 'primary_position'])

    final_path = f"{processed_dir}/cleaned_at_bats.csv"
    df_clean.to_csv(final_path, index=False)

if __name__ == "__main__":
    clean_and_map_player_ids()
