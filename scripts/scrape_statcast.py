import sys
import pandas as pd
from pybaseball import statcast_date_range
from sqlalchemy import text
from db_client import get_engine

def run(start_date, end_date):
    print(f"Pulling Statcast track logs for block window: {start_date} -> {end_date}")
    engine = get_engine()
    
    # 1. Extract raw data via pybaseball api stream interface layer
    try:
        df = statcast_date_range(start_dt=start_date, end_dt=end_date)
    except Exception as e:
        print(f"Track data range payload extract issue: {e}")
        return

    if df is None or df.empty:
        print("Empty statcast sequence encountered across date query windows.")
        return

    print(f"Parsing {len(df)} telemetry stream entries for ingestion schema...")
    
    # Fill defaults/safeties to prevent execution parsing errors
    df['launch_speed'] = pd.to_numeric(df['launch_speed'], errors='coerce')
    df['launch_angle'] = pd.to_numeric(df['launch_angle'], errors='coerce')
    df['hit_distance_sc'] = pd.to_numeric(df['hit_distance_sc'], errors='coerce')

    with engine.begin() as conn:
        for _, row in df.iterrows():
            try:
                # Direct lookup insertion strategy matches our clean 7-table design
                conn.execute(text("""
                    INSERT INTO statcast_pitches (
                        game_pk, game_date, plate_appearance_number, at_bat_number, pitch_number, inning, inning_half, outs,
                        ball_count, strike_count, batter_id, pitcher_id, pitch_type, release_velocity, release_spin_rate,
                        release_extension, release_pos_x, release_pos_y, release_pos_z, vx0, vy0, vz0, ax, ay, az, effective_speed,
                        plate_crossing_x, plate_crossing_z, sz_top, sz_bot, runner_on_first, runner_on_second, runner_on_third,
                        home_score, away_score, play_event, play_description,
                        exit_velocity, launch_angle, hit_distance, spray_angle, hit_location_x, hit_location_y, expected_woba, expected_slugging, is_hard_hit, is_sweet_spot
                    ) VALUES (
                        :game_pk, :game_date, :pa_num, :ab_num, :pitch_num, :inn, :half, :outs, :balls, :strikes, :bat_id, :pit_id, :p_type, :vel, :spin,
                        :ext, :p_x, :p_y, :p_z, :vx, :vy, :vz, :ax, :ay, :az, :eff_v, :px_x, :px_z, :sz_t, :sz_b, :on_1b, :on_2b, :on_3b,
                        :h_score, :a_score, :event, :desc,
                        :ev, :la, :dist, :spray, :loc_x, :loc_y, :xwoba, :xslug, :hard_hit, :sweet_spot
                    ) ON CONFLICT (game_pk, at_bat_number, pitch_number) DO NOTHING;
                """), {
                    "game_pk": int(row['game_pk']), "game_date": pd.to_datetime(row['game_date']).date(),
                    "pa_num": int(row.get('at_bat_number', 0)), "ab_num": int(row.get('at_bat_number', 0)),
                    "pitch_num": int(row.get('pitch_number', 0)), "inn": int(row['inning']), "half": row['inning_topbot'],
                    "outs": int(row['outs_when_up']), "balls": int(row['balls']), "strikes": int(row['strikes']),
                    "bat_id": int(row['batter']), "pit_id": int(row['pitcher']), "p_type": row['pitch_type'],
                    "vel": row['release_speed'], "spin": row['release_spin_rate'] if pd.notna(row['release_spin_rate']) else None,
                    "ext": row['release_extension'] if pd.notna(row['release_extension']) else None,
                    "p_x": row['release_pos_x'], "p_y": row['release_pos_y'], "p_z": row['release_pos_z'],
                    "vx": row['vx0'], "vy": row['vy0'], "vz": row['vz0'], "ax": row['ax'], "ay": row['ay'], "az": row['az'],
                    "eff_v": row['effective_speed'] if pd.notna(row['effective_speed']) else None,
                    "px_x": row['plate_x'], "px_z": row['plate_z'], "sz_t": row['sz_top'], "sz_b": row['sz_bot'],
                    "on_1b": pd.notna(row['on_1b']), "on_2b": pd.notna(row['on_2b']), "on_3b": pd.notna(row['on_3b']),
                    "h_score": int(row['home_score']), "a_score": int(row['away_score']), "event": row['events'], "desc": row['des'],
                    "ev": row['launch_speed'] if pd.notna(row['launch_speed']) else None,
                    "la": row['launch_angle'] if pd.notna(row['launch_angle']) else None,
                    "dist": row['hit_distance_sc'] if pd.notna(row['hit_distance_sc']) else None,
                    "spray": None, "loc_x": row['hc_x'] if pd.notna(row['hc_x']) else None, "loc_y": row['hc_y'] if pd.notna(row['hc_y']) else None,
                    "xwoba": row['estimated_woba_using_speedangle'] if pd.notna(row['estimated_woba_using_speedangle']) else None,
                    "xslug": row['estimated_slg_using_speedangle'] if pd.notna(row['estimated_slg_using_speedangle']) else None,
                    "hard_hit": row['launch_speed'] >= 95.0 if pd.notna(row['launch_speed']) else None,
                    "sweet_spot": (row['launch_angle'] >= 8.0) & (row['launch_angle'] <= 32.0) if pd.notna(row['launch_angle']) and pd.notna(row['launch_speed']) else None
                })
            except Exception as item_err:
                continue
    print("Statcast pitches data pipeline processing completed successfully.")
