import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db_client import get_engine
from sqlalchemy import text

def run(start_date=None, end_date=None):
    if not start_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        start_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = start_date
    from pybaseball import statcast
    print(f"Pulling Statcast streams between {start_date} and {end_date}...")
    raw_df = statcast(start_dt=start_date, end_dt=end_date)
    if raw_df is None or raw_df.empty: return
    raw_df = raw_df.dropna(subset=['game_pk', 'at_bat_number', 'pitch_number'])
    raw_df['pa_id'] = raw_df['game_pk'].astype(int).astype(str) + "_" + raw_df['at_bat_number'].astype(int).astype(str)
    raw_df['pitch_id'] = raw_df['pa_id'] + "_" + raw_df['pitch_number'].astype(int).astype(str)
    raw_df = raw_df.sort_values(['game_pk', 'at_bat_number', 'pitch_number'])
    engine = get_engine()
    valid_players = pd.read_sql("SELECT player_id FROM players", con=engine)['player_id'].tolist()
    
    pa_last = raw_df.groupby('pa_id').last().reset_index()
    pa_first = raw_df.groupby('pa_id').first().reset_index()
    pa_records = []
    for idx, row in pa_last.iterrows():
        f_row = pa_first[pa_first['pa_id'] == row['pa_id']].iloc[0]
        b_id = int(row['batter']) if int(row['batter']) in valid_players else None
        p_id = int(row['pitcher']) if int(row['pitcher']) in valid_players else None
        start_bases = f"{'1' if f_row['on_1b'] else '0'}{'1' if f_row['on_2b'] else '0'}{'1' if f_row['on_3b'] else '0'}"
        end_bases = f"{'1' if row['on_1b'] else '0'}{'1' if row['on_2b'] else '0'}{'1' if row['on_3b'] else '0'}"
        pa_records.append({
            "plate_appearance_id": row['pa_id'], "game_pk": int(row['game_pk']), "inning": int(row['inning']), "outs_at_start": int(f_row['outs_when_up']),
            "batter_id": b_id, "pitcher_id": p_id, "event_result": row['events'],
            "rbi_on_play": int(row['post_bat_score'] - row['bat_score']) if pd.notna(row['events']) else 0,
            "runs_scored_on_play": int((row['post_bat_score'] + row['post_fld_score']) - (row['bat_score'] + row['fld_score'])) if pd.notna(row['events']) else 0,
            "total_balls": int(row['balls']), "total_strikes": int(row['strikes']), "pitch_count_in_pa": int(row['pitch_number']), "start_base_state": start_bases, "end_base_state": end_bases
        })
    pa_df = pd.DataFrame(pa_records).drop_duplicates(subset=['plate_appearance_id'])
    with engine.begin() as conn:
        for _, r in pa_df.iterrows():
            conn.execute(text("""
                INSERT INTO plate_appearances (plate_appearance_id, game_pk, inning, outs_at_start, batter_id, pitcher_id, event_result, rbi_on_play, runs_scored_on_play, total_balls, total_strikes, pitch_count_in_pa, start_base_state, end_base_state)
                VALUES (:plate_appearance_id, :game_pk, :inning, :outs_at_start, :batter_id, :pitcher_id, :event_result, :rbi_on_play, :runs_scored_on_play, :total_balls, :total_strikes, :pitch_count_in_pa, :start_base_state, :end_base_state)
                ON CONFLICT (plate_appearance_id) DO UPDATE SET event_result = EXCLUDED.event_result, end_base_state = EXCLUDED.end_base_state;
            """), r.to_dict())

    pitches_list = []
    for idx, row in raw_df.iterrows():
        b_id = int(row['batter']) if int(row['batter']) in valid_players else None
        p_id = int(row['pitcher']) if int(row['pitcher']) in valid_players else None
        pitches_list.append({
            'pitch_id': row['pitch_id'], 'game_pk': int(row['game_pk']), 'plate_appearance_id': row['pa_id'], 'game_date': pd.to_datetime(row['game_date']).date(), 'pitch_type': row['pitch_type'],
            'at_bat_number': int(row['at_bat_number']), 'pitch_number': int(row['pitch_number']), 'release_velocity': pd.to_numeric(row['release_speed'], errors='coerce'), 'release_spin_rate': pd.to_numeric(row['release_spin_rate'], errors='coerce'),
            'release_extension': pd.to_numeric(row['release_extension'], errors='coerce'), 'release_pos_x': pd.to_numeric(row['release_pos_x'], errors='coerce'), 'release_pos_y': pd.to_numeric(row['release_pos_y'], errors='coerce'), 'release_pos_z': pd.to_numeric(row['release_pos_z'], errors='coerce'),
            'vx0': pd.to_numeric(row['vx0'], errors='coerce'), 'vy0': pd.to_numeric(row['vy0'], errors='coerce'), 'vz0': pd.to_numeric(row['vz0'], errors='coerce'), 'ax': pd.to_numeric(row['ax'], errors='coerce'), 'ay': pd.to_numeric(row['ay'], errors='coerce'), 'az': pd.to_numeric(row['az'], errors='coerce'),
            'effective_speed': pd.to_numeric(row['effective_speed'], errors='coerce'), 'inning': int(row['inning']), 'inning_half': row['inning_top_bot'], 'outs_before_pitch': int(row['outs_when_up']),
            'runner_on_first_id': int(row['on_1b']) if pd.notna(row['on_1b']) and int(row['on_1b']) in valid_players else None, 'runner_on_second_id': int(row['on_2b']) if pd.notna(row['on_2b']) and int(row['on_2b']) in valid_players else None, 'runner_on_third_id': int(row['on_3b']) if pd.notna(row['on_3b']) and int(row['on_3b']) in valid_players else None,
            'home_score_before_pitch': int(row['fld_score'] if row['inning_top_bot']=='Top' else row['bat_score']), 'away_score_before_pitch': int(row['bat_score'] if row['inning_top_bot']=='Top' else row['fld_score']),
            'sz_top': pd.to_numeric(row['sz_top'], errors='coerce'), 'sz_bot': pd.to_numeric(row['sz_bot'], errors='coerce'), 'strike_zone_location': pd.to_numeric(row['zone'], errors='coerce') if pd.notna(row['zone']) else None,
            'batter_id': b_id, 'pitcher_id': p_id, 'batter_stance': row['stand'], 'pitcher_hand': row['p_throws'], 'ball_count': int(row['balls']), 'strike_count': int(row['strikes']), 'plate_crossing_x': pd.to_numeric(row['plate_x'], errors='coerce'), 'plate_crossing_z': pd.to_numeric(row['plate_z'], errors='coerce'), 'play_event': row['events'], 'play_description': row['description']
        })
    pitches_df = pd.DataFrame(pitches_list).drop_duplicates(subset=['pitch_id'])
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM statcast_pitches WHERE game_date BETWEEN :start AND :end"), {"start": start_date, "end": end_date})
    pitches_df.to_sql("statcast_pitches", con=engine, if_exists="append", index=False)

    batted_records = []
    for idx, row in raw_df.iterrows():
        if pd.isna(row['launch_speed']) and pd.isna(row['launch_angle']): continue
        spray = None
        if pd.notna(row['hc_x']) and pd.notna(row['hc_y']): spray = np.arctan((row['hc_x'] - 125.42) / (198.27 - row['hc_y'])) * 180 / np.pi
        batted_records.append({
            'pitch_id': row['pitch_id'], 'exit_velocity': pd.to_numeric(row['launch_speed'], errors='coerce'), 'launch_angle': pd.to_numeric(row['launch_angle'], errors='coerce'),
            'hit_distance_feet': pd.to_numeric(row['hit_distance_sc'], errors='coerce') if pd.notna(row['hit_distance_sc']) else None, 'spray_angle': spray, 'hit_location_x': pd.to_numeric(row['hc_x'], errors='coerce'), 'hit_location_y': pd.to_numeric(row['hc_y'], errors='coerce'),
            'expected_woba': pd.to_numeric(row['estimated_woba_using_speedangle'], errors='coerce'), 'expected_slugging': pd.to_numeric(row['estimated_slg_using_speedangle'], errors='coerce'),
            'is_hard_hit': True if row['launch_speed'] and row['launch_speed'] >= 95.0 else False, 'is_sweet_spot': True if row['launch_angle'] and 8.0 <= row['launch_angle'] <= 32.0 else False
        })
    if batted_records:
        batted_df = pd.DataFrame(batted_records).drop_duplicates(subset=['pitch_id'])
        batted_df = batted_df[batted_df['pitch_id'].isin(pitches_df['pitch_id'])]
        batted_df.to_sql("statcast_batted_balls", con=engine, if_exists="append", index=False)

if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else None
    run(d, d)
