"""
Data Science Studio Scrum (DS3) - Milestone M1 Game Log Extraction
Description: Generates role-isolated player statistics logs stamped with active 
             team context. Automatically discovers recent game IDs dynamically.
"""
import os
import json
import time
import requests

os.makedirs("data/raw", exist_ok=True)

def extract_detailed_game_logs():
    print("==================================================================")
    print("STARTING DATA INGESTION TASK: ROLE-SEPARATED PLAYER GAME LOGS")
    print("==================================================================")
    
    schedule_matrix_path = "data/raw/mlb_games_with_players_raw.json"
    
    # 1. Dynamic Game Key Discovery Block
    if not os.path.exists(schedule_matrix_path):
        print(f"Aborting Extraction: '{schedule_matrix_path}' not found.")
        print("Please ensure src/ingest.py executes successfully before this module.")
        return
        
    with open(schedule_matrix_path, "r") as f:
        schedule_data = json.load(f)
        
    # Extract valid game primary keys from the harvested schedule matrix
    game_pk_list = [game.get("game_pk") for game in schedule_data if game.get("game_pk")]
    print(f"Discovered {len(game_pk_list)} total calendar matches across the 2023-2026 registry.")
    
    # Safe rolling cap to protect against network request time-outs in container environments.
    # We slice the list to focus on the 50 most recent historical matches during pipeline runs.
    execution_slice = game_pk_list[-50:]
    print(f"Targeting processing pass window chunk: {len(execution_slice)} matches.")
    
    all_game_logs = {}
    
    # 2. Main API Processing and Extraction Loop
    for idx, game_pk in enumerate(execution_slice, 1):
        if idx % 10 == 0:
            print(f"Scraping detailed boxscore tracking profiles: {idx}/{len(execution_slice)}...")
            
        url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                boxscore_data = response.json()
                teams = boxscore_data.get("teams", {})
                game_log_entry = {
                    "home": {"team_name": None, "batters": [], "pitchers": []}, 
                    "away": {"team_name": None, "batters": [], "pitchers": []}
                }
                
                for role in ["home", "away"]:
                    team_node = teams.get(role, {})
                    current_team_name = team_node.get("team", {}).get("name")
                    game_log_entry[role]["team_name"] = current_team_name
                    team_players = team_node.get("players", {})
                    
                    for _, player_info in team_players.items():
                        person = player_info.get("person", {})
                        stats = player_info.get("stats", {})
                        
                        # Extract Batting Metrics
                        if "batting" in stats and stats["batting"] != {}:
                            bat_stats = stats["batting"]
                            if bat_stats.get("atBats", 0) > 0 or bat_stats.get("plateAppearances", 0) > 0:
                                game_log_entry[role]["batters"].append({
                                    "player_id": person.get("id"), 
                                    "name": person.get("fullName"), 
                                    "team_name": current_team_name,
                                    "position": player_info.get("position", {}).get("abbreviation"), 
                                    "at_bats": bat_stats.get("atBats"),
                                    "runs": bat_stats.get("runs"), 
                                    "hits": bat_stats.get("hits"), 
                                    "rbi": bat_stats.get("rbi"),
                                    "walks": bat_stats.get("baseOnBalls"), 
                                    "strikeouts": bat_stats.get("strikeOuts")
                                })
                                
                        # Extract Pitching Telemetry Metrics
                        if "pitching" in stats and stats["pitching"] != {}:
                            pitch_stats = stats["pitching"]
                            if pitch_stats.get("pitchesThrown", 0) > 0:
                                game_log_entry[role]["pitchers"].append({
                                    "player_id": person.get("id"), 
                                    "name": person.get("fullName"), 
                                    "team_name": current_team_name,
                                    "innings_pitched": pitch_stats.get("inningsPitched"), 
                                    "hits_allowed": pitch_stats.get("hits"),
                                    "runs_allowed": pitch_stats.get("runs"), 
                                    "earned_runs": pitch_stats.get("earnedRuns"),
                                    "strikeouts": pitch_stats.get("strikeOuts"), 
                                    "pitches_thrown": pitch_stats.get("pitchesThrown")
                                })
                all_game_logs[str(game_pk)] = game_log_entry
                
            # Light sleep step to prevent hitting MLB StatsAPI rate blocks
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Skipping match node {game_pk} due to unexpected network error: {e}")
            
    # 3. Buffer Persistence Layer
    output_path = "data/raw/detailed_game_logs.json"
    with open(output_path, "w") as f:
        json.dump(all_game_logs, f, indent=4)
        
    print(f"\n-> SUCCESS: Extraction pass complete. {len(all_game_logs)} game logs saved to raw buffer.")
    print("==================================================================")

if __name__ == "__main__":
    extract_detailed_game_logs()
