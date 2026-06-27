import pandas as pd
from curl_cffi import requests
from io import StringIO

def fetch_team_defensive_quality(season: int = 2026):
    """
    Scrapes traditional team defensive metrics (Errors, Double Plays)
    and modern tracking-era indicators (OAA) from Baseball Savant.
    """
    # 1. Base team fielding metrics from MLB StatsAPI
    mlb_url = f"https://statsapi.mlb.com/api/v1/teams/stats?sportId=1&stats=season&group=fielding&season={season}"
    
    # 2. Savant Team Outs Above Average (OAA) custom leaderboard CSV endpoint
    savant_url = f"https://baseballsavant.mlb.com/leaderboard/custom?year={season}&type=team_fielding&filter=&sort=1&sortDir=desc&csv=true"
    
    defense_payload = {}

    # Step 1: Gather Errors and Double Plays (Official MLB API)
    res_mlb = requests.get(mlb_url)
    if res_mlb.status_code == 200:
        teams_list = res_mlb.json().get("stats", [{}])[0].get("splits", [])
        for team_node in teams_list:
            team_id = team_node.get("team", {}).get("id")
            stat = team_node.get("stat", {})
            
            defense_payload[team_id] = {
                "team_id": team_id,
                "team_name": team_node.get("team", {}).get("name"),
                "season": season,
                "errors": stat.get("errors", 0),
                "double_plays": stat.get("doublePlays", 0),
                "outs_above_average": 0, # Placeholder for step 2
                "defensive_runs_saved": None # Handled via structural estimation or projection mapping
            }

    # Step 2: Hydrate with Outs Above Average (OAA) via Savant CSV Stream (Impersonating Chrome!)
    res_savant = requests.get(savant_url, impersonate="chrome")
    
    if res_savant.status_code == 200:
        csv_data = StringIO(res_savant.text)
        try:
            df = pd.read_csv(csv_data)
            for _, row in df.iterrows():
                team_name = row.get('team_name')
                
                # SAFEGUARD: Check for None/NaN before casting to integer
                raw_oaa = row.get('outs_above_average', 0)
                if pd.isna(raw_oaa):
                    oaa = 0
                else:
                    oaa = int(raw_oaa)
                
                # Match back to payload dictionary
                for tid, data in defense_payload.items():
                    if data["team_name"].lower() in str(team_name).lower():
                        defense_payload[tid]["outs_above_average"] = oaa
                        break
        
        except pd.errors.ParserError:
            print("⚠️ Failed to parse Team Defense CSV. Baseball Savant may have blocked the request.")
        except Exception as e:
            print(f"Skipping OAA parser hydration: {e}")

    # Return a clean list of dictionaries for database insertion
    return list(defense_payload.values())
