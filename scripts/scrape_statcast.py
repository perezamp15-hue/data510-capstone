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

        if 'pitch_id' not in df.columns or df['pitch_id'].isnull().all():
            df['pitch_id'] = df['game_pk'].astype(str) + "_" + df['pitcher'].astype(str) + "_" + df['batter'].astype(str) + "_" + df['pitch_number'].astype(str)
        
        df['derived_pa_id'] = df['game_pk'].astype(str) + "_" + df['inning_topbot'].fillna('Top').astype(str) + "_" + df['at_bat_number'].astype(str)

        pitches_inserted = 0
        pa_inserted = 0
        batted_balls_inserted = 0

        # --- STEP 1: POPULATE PARENTS FIRST (plate_appearances) ---
        print("Extracting final matchup events to populate plate_appearances...")
        pa_df = df.sort_values(by=['game_pk', 'at_bat_number', 'pitch_number'])
        pa_df = pa_df.groupby('derived_pa_id').last().reset_index()

        with engine.begin() as conn:
            for _, row in pa_df.iterrows():
                pa_data = {
                    "plate_appearance_id": row.get("derived_pa_id"),
                    "game_pk": int(row.get("game_pk")) if row.get("game_pk") else None,
                    "batter_id": int(row.get("batter")) if row.get("batter") else None,
                    "pitcher_id": int(row.get("pitcher")) if row.get("pitcher") else None,
                    "at_bat_number": int(row.get("at_bat_number")) if row.get("at_bat_number") else 0,
                    "inning": int(row.get("inning")) if row.get("inning") else 1,
                    "inning_half": row.get("inning_topbot") if row.get("inning_topbot") else "Top",
                    "final_event": row.get("events"),                       
                    "total_pitches_in_pa": int(row.get("pitch_number")) if row.get("pitch_number") else 1,
                    "final_balls": int(row.get("balls")) if row.get("balls") else 0,
                    "final_strikes": int(row.get("strikes")) if row.get("strikes") else 0
                }
                
                conn.execute(text("""
                    INSERT INTO plate_appearances (
                        plate_appearance_id, game_pk, batter_id, pitcher_id, at_bat_number, 
                        inning, inning_half, final_event, total_pitches_in_pa, final_balls, final_strikes
                    )
                    VALUES (
                        :plate_appearance_id, :game_pk, :batter_id, :pitcher_id, :at_bat_number, 
                        :inning, :inning_half, :final_event, :total_pitches_in_pa, :final_balls, :final_strikes
                    )
                    ON CONFLICT (plate_appearance_id) DO UPDATE SET
                        final_event = EXCLUDED.final_event,
                        total_pitches_in_pa = EXCLUDED.total_pitches_in_pa,
                        final_balls = EXCLUDED.final_balls,
                        final_strikes = EXCLUDED.final_strikes;
                """), pa_data)
                pa_inserted += 1

        # --- STEP 2: POPULATE CHILDREN SECOND (statcast_pitches) ---
        print("Writing data stream to statcast_pitches...")
        with engine.begin() as conn:
            for _, row in df.iterrows():
                pitch_data = {
                    "pitch_id": row.get("pitch_id"),
                    "game_pk": int(row.get("game_pk")) if row.get("game_pk") else None,
                    "plate_appearance_id": row.get("derived_pa_id"),  
                    "game_date": row.get("game_date") if row.get("game_date") else start_date,
                    "pitch_type": row.get("pitch_type"),
                    "at_bat_number": int(row.get("at_bat_number")) if row.get("at_bat_number") else 0,
                    "pitch_number": int(row.get("pitch_number")) if row.get("pitch_number") else 0,
                    "release_velocity": row.get("release_speed"),
                    "release_spin_rate": row.get("release_spin_rate"),
                    "release_extension": row.get("release_extension"),
                    "release_pos_x": row.get("release_pos_x"),
                    "release_pos_y": row.get("release_pos_y"),
                    "release_pos_z": row.get("release_pos_z"),
                    "vx0": row.get("vx0"),
                    "vy0": row.get("vy0"),
                    "vz0": row.get("vz0"),
                    "ax": row.get("ax"),
                    "ay": row.get("ay"),
                    "az": row.get("az"),
                    "effective_speed": row.get("effective_speed"),
                    "inning": int(row.get("inning")) if row.get("inning") else 1,
                    "inning_half": row.get("inning_topbot") if row.get("inning_topbot") else "Top",
                    "outs_before_pitch": int(row.get("outs_when_up")) if row.get("outs_when_up") else 0,
                    "runner_on_first_id": int(row.get("on_1b")) if row.get("on_1b") else None,
                    "runner_on_second_id": int(row.get("on_2b")) if row.get("on_2b") else None,
                    "runner_on_third_id": int(row.get("on_3b")) if row.get("on_3b") else None,
                    "home_score_before_pitch": int(row.get("home_score")) if row.get("home_score") else 0,
                    "away_score_before_pitch": int(row.get("away_score")) if row.get("away_score") else 0,
                    "sz_top": row.get("sz_top"),
                    "sz_bot": row.get("sz_bot"),
                    "strike_zone_location": int(row.get("zone")) if row.get("zone") else None,
                    "batter_id": int(row.get("batter")) if row.get("batter") else None,
                    "pitcher_id": int(row.get("pitcher")) if row.get("pitcher") else None,
                    "batter_stance": row.get("stand"),
                    "pitcher_hand": row.get("p_throws"),
                    "ball_count": int(row.get("balls")) if row.get("balls") else 0,
                    "strike_count": int(row.get("strikes")) if row.get("strikes") else 0,
                    "plate_crossing_x": row.get("plate_x"),
                    "plate_crossing_z": row.get("plate_z"),
                    "play_event": row.get("events"),
                    "play_description": row.get("description")
                }
                
                conn.execute(text("""
                    INSERT INTO statcast_pitches (
                        pitch_id, game_pk, plate_appearance_id, game_date, pitch_type, at_bat_number, pitch_number,
                        release_velocity, release_spin_rate, release_extension, release_pos_x, release_pos_y, release_pos_z,
                        vx0, vy0, vz0, ax, ay, az, effective_speed, inning, inning_half, outs_before_pitch,
                        runner_on_first_id, runner_on_second_id, runner_on_third_id, home_score_before_pitch, away_score_before_pitch,
                        sz_top, sz_bot, strike_zone_location, batter_id, pitcher_id, batter_stance, pitcher_hand,
                        ball_count, strike_count, plate_crossing_x, plate_crossing_z, play_event, play_description
                    )
                    VALUES (
                        :pitch_id, :game_pk, :plate_appearance_id, :game_date, :pitch_type, :at_bat_number, :pitch_number,
                        :release_velocity, :release_spin_rate, :release_extension, :release_pos_x, :release_pos_y, :release_pos_z,
                        :vx0, :vy0, :vz0, :ax, :ay, :az, :effective_speed, :inning, :inning_half, :outs_before_pitch,
                        :runner_on_first_id, :runner_on_second_id, :runner_on_third_id, :home_score_before_pitch, :away_score_before_pitch,
                        :sz_top, :sz_bot, :strike_zone_location, :batter_id, :pitcher_id, :batter_stance, :pitcher_hand,
                        :ball_count, :strike_count, :plate_crossing_x, :plate_crossing_z, :play_event, :play_description
                    )
                    ON CONFLICT (pitch_id) DO UPDATE SET
                        plate_appearance_id = EXCLUDED.plate_appearance_id,
                        release_velocity = EXCLUDED.release_velocity,
                        plate_crossing_x = EXCLUDED.plate_crossing_x,
                        plate_crossing_z = EXCLUDED.plate_crossing_z,
                        play_event = EXCLUDED.play_event,
                        play_description = EXCLUDED.play_description;
                """), pitch_data)
                pitches_inserted += 1

        # --- STEP 3: POPULATE BATTED BALL DETAILS LAST (statcast_batted_balls) ---
        print("Filtering contact tracking elements for statcast_batted_balls...")
        batted_df = df[df['launch_speed'].notnull() | df['launch_angle'].notnull()]

        with engine.begin() as conn:
            for _, row in batted_df.iterrows():
                batted_data = {
                    "pitch_id": row.get("pitch_id"),
                    "exit_velocity": row.get("launch_speed"),       
                    "launch_angle": row.get("launch_angle"),
                    "hit_distance_feet": int(row.get("hit_distance_sc")) if row.get("hit_distance_sc") else None,
                    "spray_angle": row.get("hc_x"),                  
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

        print(f"Statcast execution finished: Saved {pitches_inserted} pitches, {pa_inserted} plate appearances, and {batted_balls_inserted} batted balls successfully.")
        
    except Exception as e:
        print(f"Statcast failed: {e}")
        pass

if __name__ == "__main__":
    s_date = sys.argv[1] if len(sys.argv) > 1 else None
    e_date = sys.argv[2] if len(sys.argv) > 2 else s_date
    run(s_date, e_date)
