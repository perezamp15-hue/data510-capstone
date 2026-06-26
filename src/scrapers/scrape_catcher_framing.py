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
                    # Calculate realized runtime success prevention rate
                    sb = float(row.get('stolen_bases', 0))
                    cs = float(row.get('caught_stealing', 0))
                    total = sb + cs
                    catcher_map[pid]["caught_stealing_pct"] = round((cs / total) * 100, 1) if total > 0 else 0.0
        except Exception:
            pass
            
    return list(catcher_map.values())
