import sys
import io
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db_client import get_engine
from sqlalchemy import text

def run(start_date=None, end_date=None):
    if not start_date or not end_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        yesterday = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = start_date or yesterday
        end_date = end_date or yesterday

    print(f"Pulling Statcast streams between {start_date} and {end_date}...")
    url = f"https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_date_gt={start_date}&game_date_lt={end_date}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status() 
        
        df = pd.read_csv(io.StringIO(response.text), low_memory=False)
        
        if df.empty:
            print("No Statcast data found for this date range.")
            return

        # Clean columns and resolve modern pandas nan variations
        df = df.replace({np.nan: None})
        
        engine = get_engine()
        try:
            valid_g_pks = pd.read_sql("SELECT game_pk FROM games", con=engine)['game_pk'].tolist()
        except Exception:
            valid_g_pks = []

        if valid_g_pks and 'game_pk' in df.columns:
            df = df[df['game_pk'].isin(valid_g_pks)]

        if df.empty:
            print("Statcast data retrieved, but no matching games found in internal database.")
            return

        # Ensure unique pitch identifiers exist 
        if 'pitch_id' not in df.columns or df['pitch_id'].isnull().all():
            # Generate a distinct composite identifier if Savant's explicit tracking row is unpopulated
            df['pitch_id'] = df['game_pk'].astype(str) + "_" + df['pitcher'].astype(str) + "_" + df['batter'].astype(str) + "_" + df['pitch_number'].astype(str)

        pitches_inserted = 0
        batted_balls_inserted = 0

        # --- LOOP 1: POPULATE ALL PITCHES (statcast_pitches) ---
        print("Writing data stream to statcast_pitches...")
        with engine.begin() as conn:
            for _, row in df.iterrows():
                # Modify column lookups here if your statcast_pitches table uses distinct naming
                pitch_data = {
                    "pitch_id": row.get("pitch_id"),
                    "game_pk": int(row.get("game_pk")),
                    "pitcher_id": int(row.get("pitcher")) if row.get("pitcher") else None,
                    "batter_id": int(row.get("batter")) if row.get("batter") else None,
                    "pitch_type": row.get("pitch_type"),
                    "release_speed": row.get("release_speed"),
                    "plate_x": row.get("plate_x"),
                    "plate_z": row.get("plate_z"),
                    "description": row.get("description"),
                    "events": row.get("events"),
                    "inning": int(row.get("inning")) if row.get("inning") else None
                }
                
                conn.execute(text("""
                    INSERT INTO statcast_pitches (pitch_id, game_pk, pitcher_id, batter_id, pitch_type, release_speed, plate_x, plate_z, description, events, inning)
                    VALUES (:pitch_id, :game_pk, :pitcher_id, :batter_id, :pitch_type, :release_speed, :plate_x, :plate_z, :description, :events, :inning)
                    ON CONFLICT (pitch_id) DO UPDATE SET
                        release_speed = EXCLUDED.release_speed,
                        plate_x = EXCLUDED.plate_x,
                        plate_z = EXCLUDED.plate_z,
                        description = EXCLUDED.description,
                        events = EXCLUDED.events;
                """), pitch_data)
                pitches_inserted += 1

        # --- LOOP 2: POPULATE CONTACT OUTCOMES (statcast_batted_balls) ---
        print("Filtering contact tracking elements for statcast_batted_balls...")
        # Only parse entries where a ball was hit into play with valid launch parameters
        batted_df = df[df['launch_speed'].notnull() | df['launch_angle'].notnull()]

        with engine.begin() as conn:
            for _, row in batted_df.iterrows():
                batted_data = {
                    "pitch_id": row.get("pitch_id"),
                    "exit_velocity": row.get("launch_speed"),       -- Savant calls exit velocity 'launch_speed'
                    "launch_angle": row.get("launch_angle"),
                    "hit_distance_feet": int(row.get("hit_distance_sc")) if row.get("hit_distance_sc") else None,
                    "spray_angle": row.get("hc_x"),                  -- Mapping coordinate fields to match table design
                    "hit_location_x": row.get("hc_y")
                }
                
                conn.execute(text("""
                    INSERT INTO statcast_batted_balls (pitch_id, exit_velocity, launch_angle, hit_distance_feet, spray_angle, hit_location_x)
                    VALUES (:pitch_id, :exit_velocity, :launch_angle, :hit_distance_feet, :spray_angle, :hit_location_x)
                    ON CONFLICT (pitch_id) DO UPDATE SET
                        exit_velocity = EXCLUDED.exit_velocity,
                        launch_angle = EXCLUDED.launch_angle,
                        hit_distance_feet = EXCLUDED.hit_distance_feet,
                        spray_angle = EXCLUDED.spray_angle,
                        hit_location_x = EXCLUDED.hit_location_x;
                """), batted_data)
                batted_balls_inserted += 1

        print(f"Statcast execution finished: Saved {pitches_inserted} pitches and {batted_balls_inserted} batted balls successfully.")
        
    except Exception as e:
        print(f"Statcast failed: {e}")
        pass

if __name__ == "__main__":
    s_date = sys.argv[1] if len(sys.argv) > 1 else None
    e_date = sys.argv[2] if len(sys.argv) > 2 else s_date
    run(s_date, e_date)
