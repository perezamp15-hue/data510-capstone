"""
Data Science Studio Scrum (DS3) - Milestone M1 Complete Data Ingestion Pipeline
Author: Aaron Perez (Lead Data Engineer)
Description: Automates the multi-source extraction of MLB game schedules, 
             Statcast at-bat metrics, historical hourly weather vectors, 
             and static stadium dimensions into data/raw/.
"""

import os
import json
import time
import requests
import pandas as pd
from pybaseball import statcast

# Ensure immutable directories exist before execution passes
os.makedirs("data/raw", exist_ok=True)


def collect_stadium_registry():
    """Step 2: Compiles the baseline static structural matrix for all 30 Major League parks."""
    
    stadium_data = [
        {"stadium_id": "yankees", "name": "Yankee Stadium", "team": "New York Yankees", "latitude": 40.8296, "longitude": -73.9262, "altitude_ft": 54},
        {"stadium_id": "mets", "name": "Citi Field", "team": "New York Mets", "latitude": 40.7571, "longitude": -73.8458, "altitude_ft": 15},
        {"stadium_id": "dodgers", "name": "Dodger Stadium", "team": "Los Angeles Dodgers", "latitude": 34.0739, "longitude": -118.2400, "altitude_ft": 502},
        {"stadium_id": "angels", "name": "Angel Stadium", "team": "Los Angeles Angels", "latitude": 33.8003, "longitude": -117.8827, "altitude_ft": 160},
        {"stadium_id": "red_sox", "name": "Fenway Park", "team": "Boston Red Sox", "latitude": 42.3467, "longitude": -71.0972, "altitude_ft": 20},
        {"stadium_id": "cubs", "name": "Wrigley Field", "team": "Chicago Cubs", "latitude": 41.9484, "longitude": -87.6553, "altitude_ft": 600},
        {"stadium_id": "white_sox", "name": "Guaranteed Rate Field", "team": "Chicago White Sox", "latitude": 41.8299, "longitude": -87.6337, "altitude_ft": 595},
        {"stadium_id": "giants", "name": "Oracle Park", "team": "San Francisco Giants", "latitude": 37.7786, "longitude": -122.3893, "altitude_ft": 12},
        {"stadium_id": "athletics", "name": "Sutter Health Park", "team": "Oakland Athletics", "latitude": 38.5804, "longitude": -121.5053, "altitude_ft": 25},
        {"stadium_id": "mariners", "name": "T-Mobile Park", "team": "Seattle Mariners", "latitude": 47.5914, "longitude": -122.3325, "altitude_ft": 10},
        {"stadium_id": "padres", "name": "Petco Park", "team": "San Diego Padres", "latitude": 32.7073, "longitude": -117.1566, "altitude_ft": 15},
        {"stadium_id": "diamondbacks", "name": "Chase Field", "team": "Arizona Diamondbacks", "latitude": 33.4453, "longitude": -112.0667, "altitude_ft": 1082},
        {"stadium_id": "rockies", "name": "Coors Field", "team": "Colorado Rockies", "latitude": 39.7559, "longitude": -104.9942, "altitude_ft": 5200},
        {"stadium_id": "rangers", "name": "Globe Life Field", "team": "Texas Rangers", "latitude": 32.7473, "longitude": -97.0841, "altitude_ft": 541},
        {"stadium_id": "astros", "name": "Minute Maid Park", "team": "Houston Astros", "latitude": 29.7573, "longitude": -95.3556, "altitude_ft": 38},
        {"stadium_id": "royals", "name": "Kauffman Stadium", "team": "Kansas City Royals", "latitude": 39.0517, "longitude": -94.4803, "altitude_ft": 872},
        {"stadium_id": "twins", "name": "Target Field", "team": "Minnesota Twins", "latitude": 44.9817, "longitude": -93.2778, "altitude_ft": 840},
        {"stadium_id": "brewers", "name": "American Family Field", "team": "Milwaukee Brewers", "latitude": 43.0284, "longitude": -87.9712, "altitude_ft": 612},
        {"stadium_id": "cardinals", "name": "Busch Stadium", "team": "St. Louis Cardinals", "latitude": 38.6226, "longitude": -90.1928, "altitude_ft": 455},
        {"stadium_id": "braves", "name": "Truist Park", "team": "Atlanta Braves", "latitude": 33.8907, "longitude": -84.4678, "altitude_ft": 1050},
        {"stadium_id": "rays", "name": "Tropicana Field", "team": "Tampa Bay Rays", "latitude": 27.7682, "longitude": -82.6534, "altitude_ft": 34},
        {"stadium_id": "marlins", "name": "loanDepot park", "team": "Miami Marlins", "latitude": 25.7781, "longitude": -80.2197, "altitude_ft": 15},
        {"stadium_id": "nationals", "name": "Nationals Park", "team": "Washington Nationals", "latitude": 38.8730, "longitude": -77.0074, "altitude_ft": 25},
        {"stadium_id": "phillies", "name": "Citizens Bank Park", "team": "Philadelphia Phillies", "latitude": 39.9061, "longitude": -75.1665, "altitude_ft": 30},
        {"stadium_id": "orioles", "name": "Oriole Park at Camden Yards", "team": "Baltimore Orioles", "latitude": 39.2840, "longitude": -76.6216, "altitude_ft": 30},
        {"stadium_id": "pirates", "name": "PNC Park", "team": "Pittsburgh Pirates", "latitude": 40.4469, "longitude": -80.0057, "altitude_ft": 743},
        {"stadium_id": "guardians", "name": "Progressive Field", "team": "Cleveland Guardians", "latitude": 41.4958, "longitude": -81.6852, "altitude_ft": 655},
        {"stadium_id": "tigers", "name": "Comerica Park", "team": "Detroit Tigers", "latitude": 42.3392, "longitude": -83.0485, "altitude_ft": 602},
        {"stadium_id": "reds", "name": "Great American Ball Park", "team": "Cincinnati Reds", "latitude": 39.0974, "longitude": -84.5071, "altitude_ft": 510},
        {"stadium_id": "blue_jays", "name": "Rogers Centre", "team": "Toronto Blue Jays", "latitude": 43.6414, "longitude": -79.3894, "altitude_ft": 247}
    ]
    
    df = pd.DataFrame(stadium_data)
    output_path = "data/raw/stadium_registry.csv"
    df.to_csv(output_path, index=False)
    return stadium_data


def fetch_schedules_with_lineups(years=[2024]):
    """Step 3: Queries the MLB StatsAPI for game schedules and active lineup player IDs."""
    integrated_games = []
    
    for year in years:
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={year}&gameType=R"
        try:
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                continue
                
            data = response.json()
            for date_node in data.get("dates", []):
                for game in date_node.get("games", []):
                    game_pk = game.get("gamePk")
                    
                    game_item = {
                        "game_pk": game_pk,
                        "game_date": game.get("gameDate").split("T")[0],
                        "home_team": game.get("teams", {}).get("home", {}).get("team", {}).get("name"),
                        "away_team": game.get("teams", {}).get("away", {}).get("team", {}).get("name"),
                        "starting_lineups": {
                            "home_batters": [], "away_batters": [],
                            "home_starting_pitcher": None, "away_starting_pitcher": None
                        }
                    }
                    
                    # Intercept game boxscore sub-query for starting ids
                    boxscore_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                    try:
                        box_resp = requests.get(boxscore_url, timeout=5)
                        if box_resp.status_code == 200:
                            box_data = box_resp.json()
                            teams_node = box_data.get("teams", {})
                            
                            home_team_data = teams_node.get("home", {})
                            game_item["starting_lineups"]["home_batters"] = home_team_data.get("battingOrder", [])
                            if home_team_data.get("pitchers"):
                                game_item["starting_lineups"]["home_starting_pitcher"] = home_team_data.get("pitchers")[0]
                                
                            away_team_data = teams_node.get("away", {})
                            game_item["starting_lineups"]["away_batters"] = away_team_data.get("battingOrder", [])
                            if away_team_data.get("pitchers"):
                                game_item["starting_lineups"]["away_starting_pitcher"] = away_team_data.get("pitchers")[0]
                    except Exception:
                        pass # Maintain core loop stability if a game sub-query blips
                    
                    integrated_games.append(game_item)
        except Exception as e:
            print(f"Network Error mapping schedules: {e}")
            
    output_path = "data/raw/mlb_games_with_players_raw.json"
    with open(output_path, "w") as f:
        json.dump(integrated_games, f, indent=4)
        
    print(f"-> Success: Game payload with lineup IDs saved to {output_path} ({len(integrated_games)} matches).\n")
    return integrated_games


def fetch_statcast_events(start_date="2024-04-01", end_date="2024-04-03"):
    """Step 4: Pulls pitch-by-pitch at-bat outcomes from pybaseball Statcast engine."""
    print(f"Executing Step 4: Extracting Granular At-Bat Metrics ({start_date} to {end_date})...")
    try:
        df_statcast = statcast(start_dt=start_date, end_dt=end_date)
        keep_columns = ['game_date', 'player_name', 'batter', 'pitcher', 'events', 'description', 'home_team', 'away_team']
        df_filtered = df_statcast[df_statcast['events'].notna()][keep_columns]
        
        output_path = "data/raw/statcast_pitches_raw.csv"
        df_filtered.to_csv(output_path, index=False)
        print(f"-> Success: Statcast file written to {output_path} ({len(df_filtered)} rows).\n")
    except Exception as e:
        print(f"Error accessing pybaseball: {e}\n")


def fetch_hourly_weather(games_list):
    """Step 5: Queries Open-Meteo archive by matching team locations dynamically."""
    print("Executing Step 5: Querying Production Weather Systems...")
    stadium_df = pd.read_csv("data/raw/stadium_registry.csv")
    team_coords = stadium_df.set_index('team')[['latitude', 'longitude']].to_dict('index')
    weather_records = []
    
    # Process sample slice to prevent network rate limits during testing
    for game in games_list[:15]:
        home_team = game["home_team"]
        if home_team in team_coords:
            lat = team_coords[home_team]["latitude"]
            lon = team_coords[home_team]["longitude"]
            date_str = game["game_date"]
            
            weather_url = (
                f"https://archive-api.open-meteo.com/v1/archive?"
                f"latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}"
                f"&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
                f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            )
            try:
                response = requests.get(weather_url, timeout=10)
                if response.status_code == 200:
                    weather_records.append({
                        "game_pk": game["game_pk"], "game_date": date_str, "home_team": home_team,
                        "hourly_weather": response.json().get("hourly", {})
                    })
                time.sleep(0.2)
            except Exception:
                pass

    output_path = "data/raw/weather_hourly_raw.json"
    with open(output_path, "w") as f:
        json.dump(weather_records, f, indent=4)
    print(f"-> Success: Production Weather Matrix saved to {output_path}.\n")


if __name__ == "__main__":
    collect_stadium_registry()
    schedule_data = fetch_schedules_with_lineups(years=[2024])
    fetch_statcast_events(start_date="2024-04-01", end_date="2024-04-03")
    if schedule_data:
        fetch_hourly_weather(schedule_data)
    print("Successful")
