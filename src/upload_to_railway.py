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

# Connect to BOTH separate destinations natively managed by Railway variables
core_engine = create_railway_engine("DATABASE_URL")
pitch_engine = create_railway_engine("PITCH_DATABASE_URL")

RAW_DATA_DIR = os.path.join("data", "raw")
os.makedirs(RAW_DATA_DIR, exist_ok=True)

# =========================================================================
# SYSTEM CONFIGURATION & DICTIONARIES
# =========================================================================
VENUE_METADATA = {
    1614: {"name": "Angel Stadium", "lat": 33.7996, "lon": -117.8890},
    3251: {"name": "Chase Field", "lat": 33.4529, "lon": -112.0387},
    4705: {"name": "Truist Park", "lat": 33.8907, "lon": -84.4678},
    2:    {"name": "Oriole Park at Camden Yards", "lat": 39.2852, "lon": -76.6201},
    3:    {"name": "Fenway Park", "lat": 42.3466, "lon": -71.0988},
    10:   {"name": "Wrigley Field", "lat": 41.9472, "lon": -87.6564},
    4:    {"name": "Guaranteed Rate Field", "lat": 41.8309, "lon": -87.6351},
    18:   {"name": "Great American Ball Park", "lat": 39.1072, "lon": -84.5077},
    5:    {"name": "Progressive Field", "lat": 41.4951, "lon": -81.6871},
    19:   {"name": "Coors Field", "lat": 39.7561, "lon": -104.9942},
    12:   {"name": "Comerica Park", "lat": 42.3390, "lon": -83.0485},
    2392: {"name": "Daikin Park", "lat": 29.7573, "lon": -95.3555}, 
    7:    {"name": "Kauffman Stadium", "lat": 39.0517, "lon": -94.4803},
    22:   {"name": "Dodger Stadium", "lat": 34.0739, "lon": -118.2400},
    4169: {"name": "loanDepot park", "lat": 25.7781, "lon": -80.2196},
    32:   {"name": "American Family Field", "lat": 43.0280, "lon": -87.9712},
    37:   {"name": "Target Field", "lat": 44.9817, "lon": -93.2778},
    3289: {"name": "Citi Field", "lat": 40.7571, "lon": -73.8458},
    3313: {"name": "Yankee Stadium", "lat": 40.8296, "lon": -73.9262},
    5385: {"name": "Sutter Health Park", "lat": 38.5804, "lon": -121.5126}, 
    2681: {"name": "Citizens Bank Park", "lat": 39.9061, "lon": -75.1665},
    31:   {"name": "PNC Park", "lat": 40.4469, "lon": -80.0057},
    2685: {"name": "Petco Park", "lat": 32.7073, "lon": -117.1567},
    2395: {"name": "Oracle Park", "lat": 37.7786, "lon": -122.3893},
    680:  {"name": "T-Mobile Park", "lat": 47.5914, "lon": -122.3325},
    2889: {"name": "Busch Stadium", "lat": 38.6226, "lon": -90.1928},
    124:  {"name": "Tropicana Field", "lat": 27.7682, "lon": -82.6534},
    4715: {"name": "Globe Life Field", "lat": 32.7473, "lon": -97.0842},
    14:   {"name": "Rogers Centre", "lat": 43.6414, "lon": -79.3894},
    3309: {"name": "Nationals Park", "lat": 38.8730, "lon": -77.0074}
}

KNOWN_PLAYERS_CACHE = {}

# =========================================================================
# CORE & PITCH STAGING HELPERS
# =========================================================================
def stage_core_dataframe(df, table_name):
    if df.empty: return
    df.to_csv(os.path.join(RAW_DATA_DIR, f"{table_name}.csv"), index=False)
    if core_engine:
        try:
            df.to_sql(name=table_name, con=core_engine, schema='public', if_exists='append', index=False)
            print(f" Staged {len(df)} rows to {table_name} inside Core DB.")
        except Exception as e:
            print(f"Core DB staging failure for {table_name}: {e}")

def stage_pitch_dataframe(df, table_name):
    if df.empty: return
    df.to_csv(os.path.join(RAW_DATA_DIR, f"{table_name}.csv"), index=False)
    if pitch_engine:
        try:
            df.to_sql(name=table_name, con=pitch_engine, schema='public', if_exists='append', index=False)
            print(f" Staged {len(df)} rows to {table_name} inside Dedicated Pitch DB.")
        except Exception as e:
            print(f"Pitch DB staging failure for {table_name}: {e}")

# =========================================================================
# METADATA & WEATHER API WRAPPERS
# =========================================================================
def fetch_player_metadata_cached(player_id):
    if player_id in KNOWN_PLAYERS_CACHE:
        return KNOWN_PLAYERS_CACHE[player_id]
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            person_node = resp.json().get("people", [])[0]
            bio_payload = {
                "player_id": player_id, "player_name": person_node.get("fullName"),
                "birth_date": person_node.get("birthDate"), "height": person_node.get("height"),
                "weight": person_node.get("weight"), "bat_side": person_node.get("batSide", {}).get("code"),      
                "throw_hand": person_node.get("pitchHand", {}).get("code"),   
                "primary_position": person_node.get("primaryPosition", {}).get("abbreviation"),
                "is_active": 1 if person_node.get("active") else 0
            }
            KNOWN_PLAYERS_CACHE[player_id] = bio_payload
            return bio_payload
    except Exception as e:
        print(f" Error extracting metadata for player {player_id}: {e}")
    return {"player_id": player_id, "bat_side": "U", "throw_hand": "U", "is_active": 0}

def fetch_weather_2hr_intervals(lat, lon, date_str, venue_name):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat, "longitude": lon, "start_date": date_str, "end_date": date_str,
        "hourly": ["temperature_2m", "relative_humidity_2m", "pressure_msl", "wind_speed_10m", "wind_direction_10m", "precipitation"],
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph"
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            hourly = resp.json().get("hourly", {})
            df = pd.DataFrame({
                "timestamp": hourly.get("time"), "temperature": hourly.get("temperature_2m"),
                "humidity": hourly.get("relative_humidity_2m"), "pressure": hourly.get("pressure_msl"),
                "wind_speed": hourly.get("wind_speed_10m"), "wind_direction": hourly.get("wind_direction_10m"),
                "precipitation_mm": hourly.get("precipitation"), "venue_name": venue_name
            })
            df['is_raining'] = df['precipitation_mm'].apply(lambda x: 1 if x > 0.0 else 0)
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            return df[df['hour'] % 2 == 0].drop(columns=['hour'])
    except Exception as e:
        print(f" Weather query encountered timeout bounds for {venue_name}: {e}")
    return pd.DataFrame()

# =========================================================================
# MODULE 1: INGEST CORE API DATA INTO STAGING TABLES
# =========================================================================
def run_daily_pipeline(target_date_str):
    master_games = []
    master_batters = []
    master_pitchers = []
    master_weather = []

    print(f"\n====== INITIATING CORE TARGET HARVEST FOR DATE: {target_date_str} ======")
    
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={target_date_str}&endDate={target_date_str}&gameType=R"
    try:
        schedule_data = requests.get(url).json()
    except Exception as e:
        print(f" Could not gather schedule index mapping for {target_date_str}: {e}")
        return

    for date_node in schedule_data.get("dates", []):
        for game in date_node.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
                
            game_id = game.get("gamePk")
            venue_id = game.get("venue", {}).get("id")
            venue_name = game.get("venue", {}).get("name")
            start_time_utc = game.get("gameDate") 
            home_team = game.get("teams", {}).get("home", {}).get("team", {}).get("name")
            away_team = game.get("teams", {}).get("away", {}).get("team", {}).get("name")
            
            print(f" Parsed Stats Sheet: {game_id} - {away_team} @ {home_team}")
            
            master_games.append({
                "game_id": game_id, "season": datetime.now().year, "game_date": target_date_str,
                "game_start_time_utc": start_time_utc, "venue_id": venue_id, "venue_name": venue_name,
                "home_team": home_team, "away_team": away_team,
                "home_score": game.get("teams", {}).get("home", {}).get("score"),
                "away_score": game.get("teams", {}).get("away", {}).get("score")
            })
            
            if venue_id in VENUE_METADATA:
                geo = VENUE_METADATA[venue_id]
                w_df = fetch_weather_2hr_intervals(geo["lat"], geo["lon"], target_date_str, venue_name)
                if not w_df.empty:
                    w_df["game_id"] = game_id
                    master_weather.append(w_df)
            
            box_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
            box_resp = requests.get(box_url)
            if box_resp.status_code == 200:
                box_data = box_resp.json()
                for side in ["home", "away"]:
                    current_team = home_team if side == "home" else away_team
                    opposing_team = away_team if side == "home" else home_team
                    players_dict = box_data.get("teams", {}).get(side, {}).get("players", {})
                    
                    for p_key, p_info in players_dict.items():
                        p_id = p_info.get("person", {}).get("id")
                        p_name = p_info.get("person", {}).get("fullName")
                        stats_block = p_info.get("stats", {})
                        
                        fetch_player_metadata_cached(p_id)
                        
                        # Process Batters
                        bat = stats_block.get("batting", {})
                        if bat and bat.get("atBats", 0) > 0:
                            total_hits = bat.get("hits", 0)
                            d, t, hr = bat.get("doubles", 0), bat.get("triples", 0), bat.get("homeRuns", 0)
                            master_batters.append({
                                "game_id": game_id, "player_id": p_id, "player_name": p_name,
                                "team_name": current_team, "opponent_name": opposing_team,
                                "at_bats": bat.get("atBats"), "rbi": bat.get("rbi", 0),
                                "singles": total_hits - (d + t + hr), "doubles": d, "triples": t, "home_runs": hr,
                                "errors": p_info.get("stats", {}).get("fielding", {}).get("errors", 0),
                                "strikeouts": bat.get("strikeouts"), "walks": bat.get("baseOnBalls")
                            })
                            
                        # Process Pitchers
                        pitch = stats_block.get("pitching", {})
                        if pitch and pitch.get("inningsPitched", "0.0") != "0.0":
                            p_hits = pitch.get("hits", 0)
                            p_d, p_t, p_hr = pitch.get("doubles", 0), pitch.get("triples", 0), pitch.get("homeRuns", 0)
                            master_pitchers.append({
                                "game_id": game_id, "player_id": p_id, "player_name": p_name,
                                "team_name": current_team, "opponent_name": opposing_team,
                                "innings_pitched": pitch.get("inningsPitched"), "rbi_allowed": pitch.get("rbi", 0),
                                "singles_allowed": p_hits - (p_d + p_t + p_hr), "doubles_allowed": p_d,
                                "triples_allowed": p_t, "home_runs_allowed": p_hr,
                                "errors": p_info.get("stats", {}).get("fielding", {}).get("errors", 0),
                                "pitches_thrown": pitch.get("pitchesThrown"), "runs_allowed": pitch.get("runs"),
                                "earned_runs": pitch.get("earnedRuns"), "strikeouts_thrown": pitch.get("strikeouts"),
                                "walks_allowed": pitch.get("baseOnBalls")
                            })
                            
    stage_core_dataframe(pd.DataFrame(master_games), "stg_fact_games_timeline")
    stage_core_dataframe(pd.DataFrame(master_batters), "stg_fact_boxscore_batters")
    stage_core_dataframe(pd.DataFrame(master_pitchers), "stg_fact_boxscore_pitchers")
    stage_core_dataframe(pd.DataFrame(list(KNOWN_PLAYERS_CACHE.values())), "stg_dim_players_metadata")
    if master_weather:
        stage_core_dataframe(pd.concat(master_weather, ignore_index=True), "stg_fact_weather_2hr_steps")

# =========================================================================
# MODULE 2: INGEST STATCAST DATA INTO STAGING TABLES
# =========================================================================
def build_pitch_result_tracking_daily(target_date_str):
    print(f"\n====== HARVESTING DAILY STATCAST PITCH METRICS FOR: {target_date_str} ======")
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
            
            # Isolated exclusively to its own destination
            stage_pitch_dataframe(pitch_tracking_df, "stg_fact_pitcher_results_granular")
    except Exception as e:
        print(f" Failed extraction during pitch matrix parsing: {e}")

# =========================================================================
# MODULE 3: THE AUTOMATED STAGING-TO-PRODUCTION TRANSITION ENGINE
# =========================================================================
def merge_staging_to_production():
    """Moves daily information seamlessly out of staging and clears the platform logs."""
    
    # 1. CORE TRANSACTION UNIT
    if core_engine:
        core_queries = [
            """
            INSERT INTO fact_games_timeline (game_id, season, game_date, game_start_time_utc, venue_id, venue_name, home_team, away_team, home_score, away_score)
            SELECT game_id, season, CAST(game_date AS DATE), game_start_time_utc, venue_id, venue_name, home_team, away_team, home_score, away_score 
            FROM stg_fact_games_timeline
            ON CONFLICT (game_id) DO UPDATE SET
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score;
            """,
            """
            INSERT INTO fact_boxscore_batters (game_id, player_id, player_name, team_name, opponent_name, at_bats, rbi, singles, doubles, triples, home_runs, errors, strikeouts, walks)
            SELECT game_id, player_id, player_name, team_name, opponent_name, at_bats, rbi, singles, doubles, triples, home_runs, errors, strikeouts, walks 
            FROM stg_fact_boxscore_batters
            ON CONFLICT (game_id, player_id) DO NOTHING;
            """,
            """
            INSERT INTO fact_boxscore_pitchers (game_id, player_id, player_name, team_name, opponent_name, innings_pitched, rbi_allowed, singles_allowed, doubles_allowed, triples_allowed, home_runs_allowed, errors, pitches_thrown, runs_allowed, earned_runs, strikeouts_thrown, walks_allowed)
            SELECT game_id, player_id, player_name, team_name, opponent_name, CAST(innings_pitched AS NUMERIC), rbi_allowed, singles_allowed, doubles_allowed, triples_allowed, home_runs_allowed, errors, pitches_thrown, runs_allowed, earned_runs, strikeouts_thrown, walks_allowed 
            FROM stg_fact_boxscore_pitchers
            ON CONFLICT (game_id, player_id) DO NOTHING;
            """,
            """
            INSERT INTO dim_players_metadata (player_id, player_name, birth_date, height, weight, bat_side, throw_hand, primary_position, is_active)
            SELECT player_id, player_name, CAST(birth_date AS DATE), height, weight, bat_side, throw_hand, primary_position, is_active 
            FROM stg_dim_players_metadata
            ON CONFLICT (player_id) DO UPDATE SET
                is_active = EXCLUDED.is_active,
                height = EXCLUDED.height,
                weight = EXCLUDED.weight,
                updated_at = CURRENT_TIMESTAMP;
            """,
            "TRUNCATE TABLE stg_fact_games_timeline;",
            "TRUNCATE TABLE stg_fact_boxscore_batters;",
            "TRUNCATE TABLE stg_fact_boxscore_pitchers;",
            "TRUNCATE TABLE stg_dim_players_metadata;"
        ]
        try:
            with core_engine.begin() as conn:
                print("\n>>> Running Core DB Production Transition (Handling Duplicates)... <<<")
                for q in core_queries: 
                    conn.execute(text(q))
            print("Success: Core databases cleanly integrated and staging truncated.")
        except Exception as e: 
            print(f"Core DB Transition Engine collapsed: {e}")

    # 2. SEPARATED PITCH TELEMETRY TRANSACTION UNIT
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
                print("\n>>> Running Dedicated Pitch DB Production Transition (Handling Duplicates)... <<<")
                for q in pitch_queries: 
                    conn.execute(text(q))
            print("Success: Statcast telemetry data safely cataloged and staging truncated.")
        except Exception as e: 
            print(f"Pitch DB Transition Engine collapsed: {e}")

# =========================================================================
# SYSTEM RUNTIME ENTRYPOINT
# =========================================================================
if __name__ == "__main__":
    # Calculate yesterday's date dynamically at runtime
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
    
    # Run data gathers
    run_daily_pipeline(target_date_str=yesterday_str)
    build_pitch_result_tracking_daily(target_date_str=yesterday_str)
    
    # Execute the final transition into production structures
    merge_staging_to_production()
