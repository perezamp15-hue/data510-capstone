import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from pybaseball import statcast
from sqlalchemy import create_engine, text

# =========================================================================
# MULTI-WAREHOUSE CONNECTION SETUP
# =========================================================================
def create_railway_engine(env_var_name):
    url = os.environ.get(env_var_name)
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url) if url else None

# Connect to BOTH separate destinations
core_engine = create_railway_engine("DATABASE_URL")
pitch_engine = create_railway_engine("PITCH_DATABASE_URL")

RAW_DATA_DIR = os.path.join("data", "raw")
os.makedirs(RAW_DATA_DIR, exist_ok=True)
KNOWN_PLAYERS_CACHE = {}

# (Keep your existing VENUE_METADATA, fetch_player_metadata_cached, and fetch_weather_2hr_intervals functions here)

# =========================================================================
# CORE DATA TARGET INGEST
# =========================================================================
def stage_core_dataframe(df, table_name):
    if df.empty: return
    df.to_csv(os.path.join(RAW_DATA_DIR, f"{table_name}.csv"), index=False)
    if core_engine:
        try:
            df.to_sql(name=table_name, con=core_engine, schema='public', if_exists='append', index=False)
            print(f" Successfully staged {table_name} to Core DB.")
        except Exception as e:
            print(f"Core DB ingest failed for {table_name}: {e}")

# =========================================================================
# PITCH DATA TARGET INGEST (Routed to Pitch Engine)
# =========================================================================
def stage_pitch_dataframe(df, table_name):
    if df.empty: return
    df.to_csv(os.path.join(RAW_DATA_DIR, f"{table_name}.csv"), index=False)
    if pitch_engine:
        try:
            df.to_sql(name=table_name, con=pitch_engine, schema='public', if_exists='append', index=False)
            print(f" Successfully staged {table_name} to Dedicated Pitch DB.")
        except Exception as e:
            print(f"Pitch DB ingest failed for {table_name}: {e}")

# =========================================================================
# MODIFIED MODULE 3: DAILY TIMELINE PIPELINE (REDUCED RE-PRINT)
# =========================================================================
def run_daily_pipeline(target_date_str):
    # ... (Keep your existing logic for fetching schedule/boxscores/weather) ...
    # ... Just ensure that at the bottom, you call stage_core_dataframe:
    
    stage_core_dataframe(pd.DataFrame(master_games), "stg_fact_games_timeline")
    stage_core_dataframe(pd.DataFrame(master_batters), "stg_fact_boxscore_batters")
    stage_core_dataframe(pd.DataFrame(master_pitchers), "stg_fact_boxscore_pitchers")
    stage_core_dataframe(pd.DataFrame(list(KNOWN_PLAYERS_CACHE.values())), "stg_dim_players_metadata")
    if master_weather:
        stage_core_dataframe(pd.concat(master_weather, ignore_index=True), "stg_fact_weather_2hr_steps")

# =========================================================================
# MODIFIED MODULE 4: GRANULAR TELEMETRY DAILY METRICS
# =========================================================================
def build_pitch_result_tracking_daily(target_date_str):
    print(f"\n>>> HARVESTING DAILY STATCAST PITCH METRICS FOR: {target_date_str} <<<")
    try:
        raw_pitches = statcast(start_dt=target_date_str, end_dt=target_date_str)
        if not raw_pitches.empty:
            cols_map = {
                'pitcher': 'pitcher_id', 'batter': 'batter_id', 'game_pk': 'game_id',
                'pitch_type': 'pitch_type', 'description': 'pitch_result', 'pitch_number': 'pitch_number',      
                'release_speed': 'release_velocity', 'release_spin_rate': 'spin_rate',    
                'pfx_x': 'horizontal_break', 'pfx_z': 'vertical_break', 'release_extension': 'extension',     
                'balls': 'count_balls', 'strikes': 'count_strikes', 'on_1b': 'runner_on_1b',
                'on_2b': 'runner_on_2b', 'on_3b': 'runner_on_3b', 'bb_type': 'batted_ball_type',       
                'launch_speed': 'exit_velocity', 'launch_angle': 'launch_angle'       
            }
            existing_cols = [col for col in cols_map.keys() if col in raw_pitches.columns]
            pitch_tracking_df = raw_pitches[existing_cols].copy()
            pitch_tracking_df.rename(columns=cols_map, inplace=True)
            
            for runner_col in ['runner_on_1b', 'runner_on_2b', 'runner_on_3b']:
                if runner_col in pitch_tracking_df.columns:
                    pitch_tracking_df[runner_col] = pitch_tracking_df[runner_col].fillna(0).apply(lambda x: 1 if x > 0 else 0)
            
            # ROUTED EXCLUSIVELY TO PITCH CLUSTER
            stage_pitch_dataframe(pitch_tracking_df, "stg_fact_pitcher_results_granular")
    except Exception as e:
        print(f" Failed execution during pitch matrix tracking: {e}")

# =========================================================================
# TWO-WAY MERGE RUNNER
# =========================================================================
def merge_staging_to_production():
    # 1. Core DB Merges
    if core_engine:
        core_queries = [
            "INSERT INTO fact_games_timeline SELECT ... ON CONFLICT DO UPDATE ...", # (Insert full SQL statements from prior step)
            "INSERT INTO fact_boxscore_batters ... ON CONFLICT DO NOTHING;",
            "INSERT INTO fact_boxscore_pitchers ... ON CONFLICT DO NOTHING;",
            "INSERT INTO dim_players_metadata ... ON CONFLICT DO UPDATE ...",
            "TRUNCATE TABLE stg_fact_games_timeline;",
            "TRUNCATE TABLE stg_fact_boxscore_batters;",
            "TRUNCATE TABLE stg_fact_boxscore_pitchers;",
            "TRUNCATE TABLE stg_dim_players_metadata;"
        ]
        try:
            with core_engine.begin() as conn:
                print("\n>>> Executing Core DB Merge Engine... <<<")
                for q in core_queries: conn.execute(text(q))
        except Exception as e: print(f"Core DB Merge Error: {e}")

    # 2. Pitch DB Merges
    if pitch_engine:
        pitch_queries = [
            """
            INSERT INTO fact_pitcher_results_granular (game_id, pitcher_id, batter_id, pitch_type, pitch_result, pitch_number, release_velocity, spin_rate, horizontal_break, vertical_break, extension, count_balls, count_strikes, runner_on_1b, runner_on_2b, runner_on_3b, batted_ball_type, exit_velocity, launch_angle)
            SELECT game_id, pitcher_id, batter_id, pitch_type, pitch_result, pitch_number, release_velocity, spin_rate, horizontal_break, vertical_break, extension, count_balls, count_strikes, runner_on_1b, runner_on_2b, runner_on_3b, batted_ball_type, exit_velocity, launch_angle 
            FROM stg_fact_pitcher_results_granular
            ON CONFLICT (game_id, pitcher_id, batter_id, pitch_number) DO NOTHING;
            """,
            "TRUNCATE TABLE stg_fact_pitcher_results_granular;"
        ]
        try:
            with pitch_engine.begin() as conn:
                print("\n>>> Executing Pitch DB Merge Engine... <<<")
                for q in pitch_queries: conn.execute(text(q))
        except Exception as e: print(f"Pitch DB Merge Error: {e}")

if __name__ == "__main__":
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
    
    run_daily_pipeline(target_date_str=yesterday_str)
    build_pitch_result_tracking_daily(target_date_str=yesterday_str)
    
    merge_staging_to_production()
