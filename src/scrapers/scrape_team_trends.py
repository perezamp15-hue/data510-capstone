import requests

def fetch_team_trends(season: int):
    """
    Scrapes every game log for a team in a given season to calculate 
    rolling trends (Last 5, 10, 20 games) for simulator context.
    """
    # StatsAPI game log endpoint for hitting and pitching team aggregates
    hit_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=gameLog&group=hitting&season={season}"
    pitch_url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/stats?stats=gameLog&group=pitching&season={season}"
    
    trends = {5: {}, 10: {}, 20: {}}
    
    res_hit = requests.get(hit_url)
    res_pitch = requests.get(pitch_url)
    
    if res_hit.status_code != 200 or res_pitch.status_code != 200:
        print(f"Error fetching logs for team {team_id}")
        return trends
        
    hit_logs = res_hit.json().get("stats", [{}])[0].get("splits", [])
    pitch_logs = res_pitch.json().get("stats", [{}])[0].get("splits", [])
    
    # Sort chronologically (most recent first)
    hit_logs.sort(key=lambda x: x.get("date"), reverse=True)
    pitch_logs.sort(key=lambda x: x.get("date"), reverse=True)
    
    # Calculate slices for 5, 10, and 20 games
    for window in [5, 10, 20]:
        if len(hit_logs) < window:
            continue  # Not enough games played in the season yet
            
        hit_slice = hit_logs[:window]
        pitch_slice = pitch_logs[:window]
        
        # --- HITTING AGGREGATES ---
        total_runs = sum(g.get("stat", {}).get("runs", 0) for g in hit_slice)
        total_ab = sum(g.get("stat", {}).get("atBats", 0) for g in hit_slice)
        total_hits = sum(g.get("stat", {}).get("hits", 0) for g in hit_slice)
        total_bb = sum(g.get("stat", {}).get("baseOnBalls", 0) for g in hit_slice)
        total_k = sum(g.get("stat", {}).get("strikeOuts", 0) for g in hit_slice)
        total_hr = sum(g.get("stat", {}).get("homeRuns", 0) for g in hit_slice)
        total_sf = sum(g.get("stat", {}).get("sacrificeFlies", 0) for g in hit_slice)
        total_hbp = sum(g.get("stat", {}).get("hitByPitch", 0) for g in hit_slice)
        total_tb = sum(g.get("stat", {}).get("totalBases", 0) for g in hit_slice)
        
        # Calculated Hitting Metrics
        pa = total_ab + total_bb + total_hbp + total_sf
        obp = (total_hits + total_bb + total_hbp) / pa if pa > 0 else 0
        slg = total_tb / total_ab if total_ab > 0 else 0
        ops = obp + slg
        
        denom_babip = (total_ab - total_k - total_hr + total_sf)
        babip = (total_hits - total_hr) / denom_babip if denom_babip > 0 else 0
        
        # --- PITCHING AGGREGATES (Bullpen Focused) ---
        # Note: To isolate the bullpen perfectly, we subtract starting pitcher stats 
        # or filter by games where the team used multiple relievers. As a reliable 
        # baseline, we pull the team's total pitching performance over this window.
        total_er = sum(g.get("stat", {}).get("earnedRuns", 0) for g in pitch_slice)
        total_ip = sum(float(g.get("stat", {}).get("inningsPitched", 0)) for g in pitch_slice)
        
        bullpen_era = (total_er * 9) / total_ip if total_ip > 0 else 0
        
        trends[window] = {
            "runs_per_game": round(total_runs / window, 2),
            "ops": round(ops, 3),
            "strikeout_pct": round((total_k / pa) * 100, 1) if pa > 0 else 0,
            "team_babip": round(babip, 3),
            "pitching_era": round(bullpen_era, 2) # Serves as our trend proxy
        }
        
    return trends
