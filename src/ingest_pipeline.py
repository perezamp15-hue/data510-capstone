"""
Data Science Studio Scrum (DS3) - Master Ingestion Engine
Description: Seeds complete 30-stadium telemetry and harvests multi-season raw data.
"""
import os
import sys
import json
import time
import requests
import pandas as pd
from sqlalchemy import create_engine
from pybaseball import statcast

def get_database_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ CRITICAL ERROR: DATABASE_URL environment variable is blank.")
        sys.exit(1)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return create_engine(db_url)

def seed_stadium_registry(engine):
    print("\n[STEP 1] Seeding Complete 30-Ballpark Reference Registry...")
    stadium_data = [
        {"stadium_id": "angels", "name": "Angel Stadium", "team": "Los Angeles Angels", "latitude": 33.8003, "longitude": -117.8827, "altitude_ft": 160},
        {"stadium_id": "astros", "name": "Minute Maid Park", "team": "Houston Astros", "latitude": 29.7573, "longitude": -95.3555, "altitude_ft": 23},
        {"stadium_id": "athletics", "name": "Sutter Health Park", "team": "Athletics", "latitude": 38.5802, "longitude": -121.5074, "altitude_ft": 45},
        {"stadium_id": "blue_jays", "name": "Rogers Centre", "team": "Toronto Blue Jays", "latitude": 43.6414, "longitude": -79.3894, "altitude_ft": 247},
        {"stadium_id": "braves", "name": "Truist Park", "team": "Atlanta Braves", "latitude": 33.8907, "longitude": -84.4678, "altitude_ft": 980},
        {"stadium_id": "brewers", "name": "American Family Field", "team": "Milwaukee Brewers", "latitude": 43.0284, "longitude": -87.9712, "altitude_ft": 600},
        {"stadium_id": "cardinals", "name": "Busch Stadium", "team": "St. Louis Cardinals", "latitude": 38.6226, "longitude": -90.1928, "altitude_ft": 455},
        {"stadium_id": "cubs", "name": "Wrigley Field", "team": "Chicago Cubs", "latitude": 41.9484, "longitude": -87.6553, "altitude_ft": 600},
        {"stadium_id": "diamondbacks", "name": "Chase Field", "team": "Arizona Diamondbacks", "latitude": 33.4453, "longitude": -112.0667, "altitude_ft": 1082},
        {"stadium_id": "dodgers", "name": "Dodger Stadium", "team": "Los Angeles Dodgers", "latitude": 34.0739, "longitude": -118.2400, "altitude_ft": 502},
        {"stadium_id": "giants", "name": "Oracle Park", "team": "San Francisco Giants", "latitude": 37.7786, "longitude": -122.3893, "altitude_ft": 8},
        {"stadium_id": "guardians", "name": "Progressive Field", "team": "Cleveland Guardians", "latitude": 41.4958, "longitude": -81.6853, "altitude_ft": 655},
        {"stadium_id": "mariners", "name": "T-Mobile Park", "team": "Seattle Mariners", "latitude": 47.5914, "longitude": -122.3325, "altitude_ft": 10},
        {"stadium_id": "marlins", "name": "loanDepot park", "team": "Miami Marlins", "latitude": 25.7781, "longitude": -80.2197, "altitude_ft": 15},
        {"stadium_id": "mets", "name": "Citi Field", "team": "New York Mets", "latitude": 40.7571, "longitude": -73.8458, "altitude_ft": 15},
        {"stadium_id": "nationals", "name": "Nationals Park", "team": "Washington Nationals", "latitude": 38.8730, "longitude": -77.0074, "altitude_ft": 25},
        {"stadium_id": "orioles", "name": "Oriole Park at Camden Yards", "team": "Baltimore Orioles", "latitude": 39.2840, "longitude": -76.6216, "altitude_ft": 30},
        {"stadium_id": "padres", "name": "Petco Park", "team": "San Diego Padres", "latitude": 32.7073, "longitude": -117.1566, "altitude_ft": 13},
        {"stadium_id": "phillies", "name": "Citizens Bank Park", "team": "Philadelphia Phillies", "latitude": 39.9061, "longitude": -75.1665, "altitude_ft": 30},
        {"stadium_id": "pirates", "name": "PNC Park", "team": "Pittsburgh Pirates", "latitude": 40.4469, "longitude": -80.0057, "altitude_ft": 743},
        {"stadium_id": "rangers", "name": "Globe Life Field", "team": "Texas Rangers", "latitude": 32.7473, "longitude": -97.0842, "altitude_ft": 616},
        {"stadium_id": "rays", "name": "Tropicana Field", "team": "Tampa Bay Rays", "latitude": 27.7682, "longitude": -82.6534, "altitude_ft": 44},
        {"stadium_id": "red_sox", "name": "Fenway Park", "team": "Boston Red Sox", "latitude": 42.3467, "longitude": -71.0972, "altitude_ft": 20},
        {"stadium_id": "reds", "name": "Great American Ball Park", "team": "Cincinnati Reds", "latitude": 39.0979, "longitude": -84.5071, "altitude_ft": 483},
        {"stadium_id": "rockies", "name": "Coors Field", "team": "Colorado Rockies", "latitude": 39.7559, "longitude": -104.9942, "altitude_ft": 5200},
        {"stadium_id": "royals", "name": "Kauffman Stadium", "team": "Kansas City Royals", "latitude": 39.0517, "longitude": -94.4803, "altitude_ft": 750},
        {"stadium_id": "tigers", "name": "Comerica Park", "team": "Detroit Tigers", "latitude": 42.3390, "longitude": -83.0485, "altitude_ft": 600},
        {"stadium_id": "twins", "name": "Target Field", "team": "Minnesota Twins", "latitude": 44.9817, "longitude": -93.2778, "altitude_ft": 840},
        {"stadium_id": "white_sox", "name": "Guaranteed Rate Field", "team": "Chicago White Sox", "latitude": 41.8299, "longitude": -87.6337, "altitude_ft": 595},
        {"stadium_id": "yankees", "name": "Yankee Stadium", "team": "New York Yankees", "latitude": 40.8296, "longitude": -73.9262, "altitude_ft": 54}
    ]
    df = pd.DataFrame(stadium_data)
    df.to_sql("stg_stadiums", con=engine, if_exists="replace", index=False)
    print(f"✅ Successfully seeded {len(df)} ballparks into stg_stadiums.")

def ingest_schedules_and_statcast(engine):
    print("\n[STEP 2] Downloading Calendars & Pitch Telemetry...")
    
    # Safe mid-season tracking boundaries across our target seasons
    seasons = [
        {"start": "2024-06-10", "end": "2024-06-12"},
        {"start": "2025-06-09", "end": "2025-06-11"}
    ]
    
    integrated_games = []
    for yr in [2024, 2025]:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={yr}&gameType=R"
        try:
            res = requests.get(url, timeout=12)
            if res.status_code == 200:
                for d_node in res.json().get("dates", []):
                    for gm in d_node.get("games", []):
                        integrated_games.append({
                            "game_pk": gm.get("gamePk"),
                            "game_date": gm.get("gameDate").split("T")[0],
                            "home_team": gm.get("teams", {}).get("home", {}).get("team", {}).get("name"),
                            "away_team": gm.get("teams", {}).get("away", {}).get("team", {}).get("name")
                        })
        except Exception as e:
            print(f"⚠️ Schedule fetch warning for {yr}: {e}")

    if not integrated_games:
        print("❌ CRITICAL: Schedule vector is empty. Ingestion halting.")
        return []

    pd.DataFrame(integrated_games).to_sql("stg_schedules", con=engine, if_exists="replace", index=False)
    print(f" Saved {len(integrated_games)} matches into stg_schedules.")

    # Harvest Statcast Records
    first_pass = True
    for chunk in seasons:
        try:
            df_sc = statcast(start_dt=chunk["start"], end_dt=chunk["end"])
            if df_sc is not None and not df_sc.empty:
                cols = ['game_date', 'batter', 'pitcher', 'events', 'description', 'home_team', 'away_team']
                df_fil = df_sc[df_sc['events'].notna()][cols]
                mode = "replace" if first_pass else "append"
                df_fil.to_sql("stg_statcast_pitches", con=engine, if_exists=mode, index=False)
                print(f" Appended {len(df_fil)} rows from block {chunk['start']}.")
                first_pass = False
        except Exception as e:
            print(f"⚠️ Statcast interface warning for {chunk['start']}: {e}")

    return [g["game_pk"] for g in integrated_games if g.get("game_pk")][-20:]

def ingest_boxscore_performance_logs(engine, target_pks):
    print(f"\n[STEP 3] Running Extraction on {len(target_pks)} Game Boxscores...")
    if not target_pks:
        print("❌ Cannot extract boxscores: Game key list is empty.")
        return

    flattened_logs = []
    for pk in target_pks:
        url = f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                flattened_logs.append({"game_pk": pk, "log_data": json.dumps(resp.json().get("teams", {}))})
        except Exception as e:
            print(f"⚠️ Skipping boxscore lookup for {pk}: {e}")
        time.sleep(0.05)
        
    if flattened_logs:
        pd.DataFrame(flattened_logs).to_sql("stg_game_logs", con=engine, if_exists="replace", index=False)
        print(f" Streamed {len(flattened_logs)} records into stg_game_logs.")

if __name__ == "__main__":
    db_engine = get_database_engine()
    seed_stadium_registry(db_engine)
    active_pks = ingest_schedules_and_statcast(db_engine)
    ingest_boxscore_performance_logs(db_engine, active_pks)
    print("\n✅ INGESTION PIPELINE TASK COMPLETED SUCCESSFULLY.")
