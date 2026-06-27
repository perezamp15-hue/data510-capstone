import requests

def fetch_team_trends(team_id: int, season: int):
    """
    Scrapes every game log for a team in a given season to calculate 
    rolling trends (Last 5, 10, 20 games) for simulator context.
    """
    # FIXED: Handled the missing parameter NameError by adding team_id
    hit_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=gameLog&group=hitting&season={season}"
    pitch_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=gameLog&group=pitching&season={season}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    trends = {5: {}, 10: {}, 20: {}}
    
    try:
        res_hit = requests.get(hit_url, headers=headers, timeout=12)
        res_pitch = requests.get(pitch_url, headers=headers, timeout=12)
        if res_hit.status_code != 200 or res_pitch.status_code != 200:
            return trends
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection timeout fetching team logs for team {team_id}: {e}")
        return trends
        
    hit_logs = res_hit.json().get("stats", [{}])[0].get("splits", [])
    pitch_logs = res_pitch.json().get("stats", [{}])[0].get("splits", [])
    
    # Sort chronologically (most recent first)
    hit_logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    pitch_logs.sort(key=lambda x: x.get("date", ""), reverse=True)
    
    def normalize_innings(ip_list):
        """Converts base-3 baseball innings strings safely into true decimal values."""
        total_outs = 0
        for ip_val in ip_list:
            try:
                ip_str = str(ip_val)
                if "." in ip_str:
                    full_innings, outs = ip_str.split(".")
                    total_outs += (int(full_innings) * 3) + int(outs)
                else:
                    total_outs += int(ip_val) * 3
            except (ValueError, TypeError):
                continue
        return total_outs / 3.0

    # Calculate slices for 5, 10, and 20 games
    for window in [5, 10, 20]:
        if len(hit_logs) < window or len(pitch_logs) < window:
            continue  
            
        hit_slice = hit_logs[:window]
        pitch_slice = pitch_logs[:window]
        
        # --- HITTING AGGREGATES ---
        total_runs = sum(int(g.get("stat", {}).get("runs", 0) or 0) for g in hit_slice)
        total_ab = sum(int(g.get("stat", {}).get("atBats", 0) or 0) for g in hit_slice)
        total_hits = sum(int(g.get("stat", {}).get("hits", 0) or 0) for g in hit_slice)
        total_bb = sum(int(g.get("stat", {}).get("baseOnBalls", 0) or 0) for g in hit_slice)
        total_k = sum(int(g.get("stat", {}).get("strikeOuts", 0) or 0) for g in hit_slice)
        total_hr = sum(int(g.get("stat", {}).get("homeRuns", 0) or 0) for g in hit_slice)
        total_sf = sum(int(g.get("stat", {}).get("sacrificeFlies", 0) or 0) for g in hit_slice)
        total_hbp = sum(int(g.get("stat", {}).get("hitByPitch", 0) or 0) for g in hit_slice)
        total_tb = sum(int(g.get("stat", {}).get("totalBases", 0) or 0) for g in hit_slice)
        
        pa = total_ab + total_bb + total_hbp + total_sf
        obp = (total_hits + total_bb + total_hbp) / pa if pa > 0 else 0
        slg = total_tb / total_ab if total_ab > 0 else 0
        ops = obp + slg
        
        denom_babip = (total_ab - total_k - total_hr + total_sf)
        babip = (total_hits - total_hr) / denom_babip if denom_babip > 0 else 0
        
        # --- PITCHING AGGREGATES ---
        total_er = sum(int(g.get("stat", {}).get("earnedRuns", 0) or 0) for g in pitch_slice)
        
        # FIXED: Enforced baseball base-3 innings aggregation logic to avoid math distortion
        raw_ips = [g.get("stat", {}).get("inningsPitched", 0) for g in pitch_slice]
        true_ip = normalize_innings(raw_ips)
        
        pitching_era = (total_er * 9) / true_ip if true_ip > 0 else 0
        
        trends[window] = {
            "runs_per_game": round(total_runs / window, 2),
            "ops": round(ops, 3),
            "strikeout_pct": round((total_k / pa) * 100, 1) if pa > 0 else 0,
            "team_babip": round(babip, 3),
            "pitching_era": round(pitching_era, 2) 
        }
        
    return trends
