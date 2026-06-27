import pandas as pd
from curl_cffi import requests
from io import StringIO

# Cache memory matrix to avoid hitting Baseball Savant repeatedly inside a player loop
_CATCHER_CACHE = {}

def fetch_catcher_framing_metrics(player_id: int, season: int):
    """
    Scrapes advanced Statcast catcher metrics (Framing Runs, Strike %, 
    Pop Time, Caught Stealing %) directly from Baseball Savant leaderboards.
    Filters global leaderboard down dynamically to individual player requests.
    """
    global _CATCHER_CACHE
    
    # If cache is empty or for a different season, populate it with the bulk download
    if not _CATCHER_CACHE or _CATCHER_CACHE.get("season_key") != season:
        _CATCHER_CACHE = {"season_key": season, "data": {}}
        
        framing_url = f"https://baseballsavant.mlb.com/leaderboard/catcher-framing?year={season}&type=catcher&sort=4&sortDir=desc&csv=true"
        pop_url = f"https://baseballsavant.mlb.com/leaderboard/poptime?year={season}&team=&min_throws=0&csv=true"
        
        # 1. Fetch Framing Data Matrix
        try:
            res_frame = requests.get(framing_url, impersonate="chrome", timeout=15)
            if res_frame.status_code == 200 and "player_id" in res_frame.text:
                df_frame = pd.read_csv(StringIO(res_frame.text))
                for _, row in df_frame.iterrows():
                    raw_pid = row.get('player_id')
                    if pd.isna(raw_pid):
                        continue
                    pid = int(raw_pid)
                    
                    _CATCHER_CACHE["data"][pid] = {
                        "player_id": pid,
                        "season": season,
                        "framing_runs": float(row.get('catcher_framing_runs', 0.0) or 0.0),
                        "strike_percentage": float(row.get('strike_rate', 0.0) or 0.0),
                        "pop_time": None,         
                        "caught_stealing_pct": 0.0 
                    }
        except Exception as e:
            print(f"Error parsing framing leaderboard layer from Savant: {e}")

        # 2. Fetch and Merge Pop Time / Arm Strength Data Matrix
        try:
            res_pop = requests.get(pop_url, impersonate="chrome", timeout=15)
            if res_pop.status_code == 200 and "player_id" in res_pop.text:
                df_pop = pd.read_csv(StringIO(res_pop.text))
                for _, row in df_pop.iterrows():
                    raw_pid = row.get('player_id')
                    if pd.isna(raw_pid):
                        continue
                    pid = int(raw_pid)
                    
                    # Ensure structural payload initialization exists
                    if pid not in _CATCHER_CACHE["data"]:
                        _CATCHER_CACHE["data"][pid] = {
                            "player_id": pid,
                            "season": season,
                            "framing_runs": 0.0,
                            "strike_percentage": 0.0,
                            "pop_time": None,
                            "caught_stealing_pct": 0.0
                        }
                    
                    _CATCHER_CACHE["data"][pid]["pop_time"] = float(row.get('pop_time_2b', 0.0) or 0.0)
                    
                    sb = float(row.get('stolen_bases', 0) or 0.0)
                    cs = float(row.get('caught_stealing', 0) or 0.0)
                    total_attempts = sb + cs
                    
                    _CATCHER_CACHE["data"][pid]["caught_stealing_pct"] = round(
                        (cs / total_attempts) * 100 if total_attempts > 0 else 0.0, 1
                    )
        except Exception as e:
            print(f"Error parsing pop time leaderboard layer from Savant: {e}")

    # Return individual catcher lookup or structural fallbacks
    return _CATCHER_CACHE["data"].get(player_id, {
        "player_id": player_id,
        "season": season,
        "framing_runs": 0.0,
        "strike_percentage": 0.0,
        "pop_time": None,
        "caught_stealing_pct": 0.0
    })
