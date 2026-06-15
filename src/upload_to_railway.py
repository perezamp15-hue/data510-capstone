import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
from pybaseball import statcast
from sqlalchemy import create_engine, text

# =========================================================================
# WAREHOUSE CONNECTION SETUP
# =========================================================================
# Railway provides DATABASE_URL automatically if referenced properly.
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://'
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    print("WARNING: DATABASE_URL not found. Data will only save locally to CSV.")
    engine = None
else:
    engine = create_engine(DATABASE_URL)

# Local backup directory
RAW_DATA_DIR = os.path.join("data", "raw")
os.makedirs(RAW_DATA_DIR, exist_ok=True)

# Metadata cache
KNOWN_PLAYERS_CACHE = {}

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

# =========================================================================
# HELPER: LAND TO STAGING
# =========================================================================
def stage_dataframe(df, table_name):
    """Saves data to a local CSV backup and appends it to the Postgres warehouse."""
    if df.empty:
        return
        
    # 1. Local backup save
    csv_path = os.path.join(RAW_DATA_DIR, f"{table_name}.csv")
    df.to_csv(csv_path, index=False)
    
    # 2. Database upload layer
    if engine:
        try:
            print(f"Uploading {len(df)} rows to staging table: {table_name}...")
            # 'append' adds the daily batch logs cleanly without wiping historical execution rows
            df.to_sql(name=table_name, con=engine, schema='public', if_exists='append', index=False)
            print(f" Successfully staged {table_name}.")
        except Exception as e:
            print(f"Database ingest failed for {table_name}: {e}")

# =========================================================================
# MODULE 1 & 2: REUSED SUB-FUNCTIONS
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
        print(f" Failed retrieving profile for player {player_id}: {e}")
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
        print(f" Weather query timed out for {venue_name}: {e}")
    return pd.DataFrame()

# =========================================================================
# MODIFIED MODULE 3: DAILY TIMELINE PIPELINE
# =========================================================================
def run_daily_pipeline(target_date_str):
    """Pulls schedule and stats for ONE specific day."""
    master_games = []
    master_batters = []
    master_pitchers = []
    master_weather = []

    print(f"\n====== INITIATING TARGET LOG HARVEST FOR DATE: {target_date_str} ======")
    
    # Hit schedule endpoint strictly isolated to the target calendar date string
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={target_date_str}&endDate={target_date_str}&gameType=R"
    try:
        schedule_data = requests.get(url).json()
    except Exception as e:
        print(f" Could not grab schedule data for {target_date_str}: {e}")
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
            
            print(f" Processing Game: {game_id} - {away_team} @ {home_team}")
            
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
                        
                        # Batters
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
                            
                        # Pitchers
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
    
    # Commit Batches to Database Warehouse
    stage_dataframe(pd.DataFrame(master_games), "stg_fact_games_timeline")
    stage_dataframe(pd.DataFrame(master_batters), "stg_fact_boxscore_batters")
    stage_dataframe(pd.DataFrame(master_pitchers), "stg_fact_boxscore_pitchers")
    stage_dataframe(pd.DataFrame(list(KNOWN_PLAYERS_CACHE.values())), "stg_dim_players_metadata")
    if master_weather:
        stage_dataframe(pd.concat(master_weather, ignore_index=True), "stg_fact_weather_2hr_steps")

# =========================================================================
# MODIFIED MODULE 4: GRANULAR TELEMETRY DAILY METRICS
# =========================================================================
def build_pitch_result_tracking_daily(target_date_str):
    """Queries Statcast for only the target date."""
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
            
            stage_dataframe(pitch_tracking_df, "stg_fact_pitcher_results_granular")
    except Exception as e:
        print(f" Failed execution during pitch matrix tracking: {e}")

# =========================================================================
# RUNTIME ORCHESTRATOR
# =========================================================================
if __name__ == "__main__":
    # Dynamically extract yesterday relative to system run date
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
    
    # 1. Gather schedule metrics for yesterday only
    run_daily_pipeline(target_date_str=yesterday_str)
    
    # 2. Gather pitch analytics for yesterday only
    build_pitch_result_tracking_daily(target_date_str=yesterday_str)
