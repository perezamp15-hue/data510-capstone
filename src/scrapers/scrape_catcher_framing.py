import pandas as pd
import requests

def fetch_catcher_framing_metrics(season: int = 2026):
    """
    Scrapes advanced Statcast catcher metrics (Framing Runs, Strike %, 
    Pop Time, Caught Stealing %) directly from Baseball Savant.
    """
    # 1. Savant Catcher Framing Leaderboard
    framing_url = f"https://baseballsavant.mlb.com/leaderboard/catcher-framing?year={season}&type=catcher&sort=4&sortDir=desc&csv=true"
    
    # 2. Savant Pop Time / Arm Strength Leaderboard
    pop_url = f"https://baseballsavant.mlb.com/leaderboard/poptime?year={season}&team=&min_throws=0&csv=true"
    
    catcher_map = {}
    
    # Process Framing & Strike %
    res_frame = requests.get(framing_url)
    if res_frame.status_code == 200:
        from io import StringIO
        df_frame = pd.read_csv(StringIO(res_frame.text))
        for _, row in df_frame.iterrows():
            pid = int(row.get('player_id'))
            catcher_map[pid] = {
                "player_id": pid,
                "season": season,
                "framing_runs": float(row.get('catcher_framing_runs', 0.0)),
                "strike_percentage": float(row.get('strike_rate', 0.0)),
                "pop_time": None,         # Placeholder for Step 2
                "caught_stealing_pct": 0.0 # Placeholder for Step 2
            }
            
    # Process Pop Time & Caught Stealing %
    res_pop = requests.get(pop_url)
    if res_pop.status_code == 200:
        from io import StringIO
        try:
            df_pop = pd.read_csv(StringIO(res_pop.text))
            for _, row in df_pop.iterrows():
                pid = int(row.get('player_id'))
                if pid in catcher_map:
                    catcher_map[pid]["pop_time"] = float(row.get('pop_time_2b', 0.0))
                    
                    # SAFEGUARD: Calculate realized runtime success prevention rate safely
                    sb = float(row.get('stolen_bases', 0))
                    cs = float(row.get('caught_stealing', 0))
                    total_attempts = sb + cs
                    
                    # Prevent ZeroDivisionError
                    catcher_map[pid]["caught_stealing_pct"] = (
                        (cs / total_attempts) * 100 if total_attempts > 0 else 0.0
                    )
        except Exception as e:
            print(f"Error parsing pop time CSV: {e}")
    return list(catcher_map.values())
