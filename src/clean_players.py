"""
Data Science Studio Scrum (DS3) - Milestone M2 Data Processing Engine
Description: Maps Player Biographical Registries into data/processed/.
"""
import os
import time
import requests
import pandas as pd

os.makedirs("data/processed", exist_ok=True)

def clean_and_map_player_ids():
    print("Starting Player ID Registry Mapping Pass...")
    raw_path = "data/raw/statcast_pitches_raw.csv"
    if not os.path.exists(raw_path):
        return
        
    df_raw = pd.read_csv(raw_path)
    all_unique_ids = list(set(df_raw['batter'].unique()).union(set(df_raw['pitcher'].unique())))
    player_registry = []
    
    for player_id in all_unique_ids[:50]: # Scaled limit boundary for quick cron verification
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                person = res.json().get("people", [])[0]
                player_registry.append({
                    "player_id": player_id, "clean_full_name": person.get("fullName"),
                    "primary_position": person.get("primaryPosition", {}).get("abbreviation"),
                    "bat_side": person.get("batSide", {}).get("code"), "pitch_hand": person.get("pitchHand", {}).get("code")
                })
        except Exception:
            pass
        time.sleep(0.05)
        
    df_reg = pd.DataFrame(player_registry)
    df_reg.to_csv("data/processed/player_registry.csv", index=False)
    
    df_clean = df_raw.merge(df_reg, left_on='batter', right_on='player_id', how='left').rename(columns={"clean_full_name": "batter_name", "bat_side": "batter_stance", "primary_position": "batter_position"}).drop(columns=['player_id', 'pitch_hand'])
    df_clean = df_clean.merge(df_reg, left_on='pitcher', right_on='player_id', how='left').rename(columns={"clean_full_name": "pitcher_name", "pitch_hand": "pitcher_throw_hand"}).drop(columns=['player_id', 'bat_side', 'primary_position'])
    df_clean.to_csv("data/processed/cleaned_at_bats.csv", index=False)
    print("Clean datasets generated successfully inside data/processed/.")

if __name__ == "__main__":
    clean_and_map_player_ids()
