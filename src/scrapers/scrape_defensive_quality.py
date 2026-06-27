import pandas as pd
from curl_cffi import requests
from io import StringIO

# In-memory execution layer cache matrix
_DEFENSE_CACHE = {}

def fetch_team_trends(team_id: int, season: int):
    """
    Scrapes traditional team defensive metrics (Errors, Double Plays)
    and modern tracking-era indicators (OAA) from Baseball Savant.
    Caches results dynamically to optimize system runtime resources.
    """
    global _DEFENSE_CACHE

    # If the cache is empty or for a different season, populate it with a bulk request
    if not _DEFENSE_CACHE or _DEFENSE_CACHE.get("season_key") != season:
        _DEFENSE_CACHE = {"season_key": season, "data": {}}
        
        mlb_url = f"https://statsapi.mlb.com/api/v1/teams/stats?sportId=1&stats=season&group=fielding&season={season}"
        savant_url = f"https://baseballsavant.mlb.com/leaderboard/custom?year={season}&type=team_fielding&filter=&sort=1&sortDir=desc&csv=true"
        
        defense_payload = {}

        # Step 1: Gather Errors and Double Plays (Official MLB API)
        try:
            res_mlb = requests.get(mlb_url, timeout=10)
            if res_mlb.status_code == 200:
                teams_list = res_mlb.json().get("stats", [{}])[0].get("splits", [])
                for team_node in teams_list:
                    tid = team_node.get("team", {}).get("id")
                    stat = team_node.get("stat", {})
                    
                    defense_payload[tid] = {
                        "team_id": tid,
                        "team_name": team_node.get("team", {}).get("name"),
                        "season": season,
                        "errors": stat.get("errors", 0),
                        "double_plays": stat.get("doublePlays", 0),
                        "outs_above_average": 0, 
                        "defensive_runs_saved": 0.0 
                    }
        except Exception as e:
            print(f"Error pulling base team fielding metrics from MLB API: {e}")

        # Step 2: Hydrate with Outs Above Average (OAA) via Savant CSV Stream
        try:
            res_savant = requests.get(savant_url, impersonate="chrome", timeout=15)
            if res_savant.status_code == 200 and "team_name" in res_savant.text:
                df = pd.read_csv(StringIO(res_savant.text))
                for _, row in df.iterrows():
                    savant_tname = str(row.get('team_name', '')).lower()
                    raw_oaa = row.get('outs_above_average', 0)
                    oaa = int(raw_oaa) if not pd.isna(raw_oaa) else 0
                    
                    # Fuzzy match string tokens to cleanly connect team configurations
                    for tid, data in defense_payload.items():
                        clean_mlb_name = data["team_name"].lower()
                        if clean_mlb_name in savant_tname or savant_tname in clean_mlb_name:
                            defense_payload[tid]["outs_above_average"] = oaa
                            break
        except Exception as e:
            print(f"Skipping OAA leaderboard hydration: {e}")

        _DEFENSE_CACHE["data"] = defense_payload

    # Return individual team stats payload or clear system fallback structured model
    return _DEFENSE_CACHE["data"].get(team_id, {
        "team_id": team_id,
        "season": season,
        "errors": 0,
        "double_plays": 0,
        "outs_above_average": 0,
        "defensive_runs_saved": 0.0
    })
