"""
Data Science Studio Scrum (DS3) - Milestone M1 Game Log Extraction
Description: Generates role-isolated player statistics logs stamped with active team context.
"""
import os
import json
import requests

os.makedirs("data/raw", exist_ok=True)

def extract_detailed_game_logs(game_pk_list=[747031]):
    print("Starting Role-Separated Game Log Ingestion...")
    all_game_logs = {}
    for game_pk in game_pk_list:
        url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                boxscore_data = response.json()
                teams = boxscore_data.get("teams", {})
                game_log_entry = {"home": {"team_name": None, "batters": [], "pitchers": []}, "away": {"team_name": None, "batters": [], "pitchers": []}}
                
                for role in ["home", "away"]:
                    team_node = teams.get(role, {})
                    current_team_name = team_node.get("team", {}).get("name")
                    game_log_entry[role]["team_name"] = current_team_name
                    team_players = team_node.get("players", {})
                    
                    for _, player_info in team_players.items():
                        person = player_info.get("person", {})
                        stats = player_info.get("stats", {})
                        
                        if "batting" in stats and stats["batting"] != {}:
                            bat_stats = stats["batting"]
                            if bat_stats.get("atBats", 0) > 0 or bat_stats.get("plateAppearances", 0) > 0:
                                game_log_entry[role]["batters"].append({
                                    "player_id": person.get("id"), "name": person.get("fullName"), "team_name": current_team_name,
                                    "position": player_info.get("position", {}).get("abbreviation"), "at_bats": bat_stats.get("atBats"),
                                    "runs": bat_stats.get("runs"), "hits": bat_stats.get("hits"), "rbi": bat_stats.get("rbi"),
                                    "walks": bat_stats.get("baseOnBalls"), "strikeouts": bat_stats.get("strikeOuts")
                                })
                        if "pitching" in stats and stats["pitching"] != {}:
                            pitch_stats = stats["pitching"]
                            if pitch_stats.get("pitchesThrown", 0) > 0:
                                game_log_entry[role]["pitchers"].append({
                                    "player_id": person.get("id"), "name": person.get("fullName"), "team_name": current_team_name,
                                    "innings_pitched": pitch_stats.get("inningsPitched"), "hits_allowed": pitch_stats.get("hits"),
                                    "runs_allowed": pitch_stats.get("runs"), "earned_runs": pitch_stats.get("earnedRuns"),
                                    "strikeouts": pitch_stats.get("strikeOuts"), "pitches_thrown": pitch_stats.get("pitchesThrown")
                                })
                all_game_logs[str(game_pk)] = game_log_entry
        except Exception as e:
            print(f"Error: {e}")
            
    with open("data/raw/detailed_game_logs.json", "w") as f:
        json.dump(all_game_logs, f, indent=4)

if __name__ == "__main__":
    extract_detailed_game_logs()
