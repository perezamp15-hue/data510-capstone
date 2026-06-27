import requests
from datetime import datetime

def fetch_bullpen_metrics(player_id: int, season: int):
    """
    Scrapes high-leverage relief metrics, situational data (Saves/Holds/Inherited Runners),
    and current workload tracking parameters for a bullpen arm.
    """
    # Clean parameter formatting using the provided player_id
    base_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=season&group=pitching&season={season}"
    adv_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=statAdvanced&group=pitching&season={season}"
    log_url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=pitching&season={season}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

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
    try:
        res_base = requests.get(base_url, headers=headers, timeout=10)
        if res_base.status_code == 200:
            splits = res_base.json().get("stats", [{}])[0].get("splits", [])
            if splits:
                stat = splits[0].get("stat", {})
                payload["era"] = stat.get("era")
                
                sv = stat.get("saves", 0)
                sv_opp = stat.get("saveOpportunities", 0)
                payload["save_percentage"] = round((sv / sv_opp) * 100, 1) if sv_opp > 0 else 0.0
                
                holds = stat.get("holds", 0)
                payload["hold_percentage"] = round((holds / max(1, sv_opp)) * 100, 1) if sv_opp > 0 else 0.0
    except Exception as e:
        print(f"Error pulling base bullpen stats for {player_id}: {e}")
    # Step 2: Parse Advanced Stats (Inherited Runners)
    try:
        res_adv = requests.get(adv_url, headers=headers, timeout=10)
        if res_adv.status_code == 200:
            splits = res_adv.json().get("stats", [{}])[0].get("splits", [])
            if splits:
                stat = splits[0].get("stat", {})
                payload["inherited_runners"] = stat.get("inheritedRunners", 0)
                payload["inherited_runners_scored"] = stat.get("inheritedRunnersScored", 0)
    except Exception as e:
        print(f"Error pulling advanced bullpen stats for {player_id}: {e}")

    # Step 3: Parse Recent Usage/Workload from Game Logs
    try:
        res_log = requests.get(log_url, headers=headers, timeout=10)
        if res_log.status_code == 200:
            logs = res_log.json().get("stats", [{}])[0].get("splits", [])
            if logs:
                # Filter out entries with missing dates before sorting
                valid_logs = [l for l in logs if l.get("date")]
                if valid_logs:
                    valid_logs.sort(key=lambda x: x.get("date"), reverse=True)
                    most_recent_game = valid_logs[0]
                    
                    payload["last_appearance_date"] = most_recent_game.get("date")
                    payload["last_pitch_count"] = most_recent_game.get("stat", {}).get("pitchesThrown", 0)
                    
                    if payload["last_appearance_date"]:
                        last_date = datetime.strptime(payload["last_appearance_date"], "%Y-%m-%d")
                        delta_days = (datetime.today() - last_date).days - 1
                        payload["days_rest"] = max(0, delta_days) # Safeguard against negative timezone drift
    except Exception as e:
        print(f"Error pulling bullpen game logs for {player_id}: {e}")

    return payload
