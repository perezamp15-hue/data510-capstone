import requests
from datetime import datetime

def fetch_bullpen_metrics(season: int):
    """
    Scrapes high-leverage relief metrics, situational data (Saves/Holds/Inherited Runners),
    and current workload tracking parameters for a bullpen arm.
    """
    # 1. Standard pitching stats for ERA, Saves, Holds
    base_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group=pitching&season={season}"
    
    # 2. Advanced pitching stats for Inherited Runners and Inherited Runners Scored (IRS)
    adv_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statAdvanced&group=pitching&season={season}"
    
    # 3. Game log to calculate rest and recent pitch counts
    log_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=pitching&season={season}"

    payload = {
        "player_id": player_id,
        "season": season,
        # --- Workload & Rest ---
        "last_appearance_date": None,
        "last_pitch_count": 0,
        "days_rest": None,
        # --- Run Prevention ---
        "era": None,
        # --- Leverage & Clutchness ---
        "inherited_runners": 0,
        "inherited_runners_scored": 0,
        "save_percentage": 0.0,
        "hold_percentage": 0.0
    }

    # Step 1: Parse Base Seasonal Stats (Saves, Holds, ERA)
    res_base = requests.get(base_url)
    if res_base.status_code == 200:
        splits = res_base.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            payload["era"] = stat.get("era")
            
            sv = stat.get("saves", 0)
            sv_opp = stat.get("saveOpportunities", 0)
            payload["save_percentage"] = round((sv / sv_opp) * 100, 1) if sv_opp > 0 else 0.0
            
            # Holds are tracked explicitly by MLB under holds
            holds = stat.get("holds", 0)
            # Hold opportunities can be derived or stated natively depending on the tracking year
            payload["hold_percentage"] = round((holds / max(1, sv_opp)) * 100, 1) if sv_opp > 0 else 0.0

    # Step 2: Parse Advanced Stats (Inherited Runners)
    res_adv = requests.get(adv_url)
    if res_adv.status_code == 200:
        splits = res_adv.json().get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            payload["inherited_runners"] = stat.get("inheritedRunners", 0)
            payload["inherited_runners_scored"] = stat.get("inheritedRunnersScored", 0)

    # Step 3: Parse Recent Usage/Workload from Game Logs
    res_log = requests.get(log_url)
    if res_log.status_code == 200:
        logs = res_log.json().get("stats", [{}])[0].get("splits", [])
        if logs:
            # Sort chronologically to grab the absolute most recent game
            logs.sort(key=lambda x: x.get("date"), reverse=True)
            most_recent_game = logs[0]
            
            payload["last_appearance_date"] = most_recent_game.get("date")
            payload["last_pitch_count"] = most_recent_game.get("stat", {}).get("pitchesThrown", 0)
            
            if payload["last_appearance_date"]:
                last_date = datetime.strptime(payload["last_appearance_date"], "%Y-%m-%d")
                payload["days_rest"] = (datetime.today() - last_date).days - 1

    return payload
