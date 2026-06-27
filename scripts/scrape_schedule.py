import pandas as pd
from db_client import get_engine, fetch_api_json

def run(season=2026):
    print(f"Importing core framework schedule for {season} season...")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&season={season}"
    data = fetch_api_json(url)
    
    schedules = []
    for date_obj in data.get("dates", []):
        for g in date_obj.get("games", []):
            schedules.append({
                "game_pk": g.get("gamePk"),
                "date": date_obj.get("date"),
                "home_team": g.get("teams", {}).get("home", {}).get("team", {}).get("name"),
                "away_team": g.get("teams", {}).get("away", {}).get("team", {}).get("name"),
                "doubleheader": True if g.get("doubleHeader") in ["Y", "S"] else False
            })
            
    if schedules:
        pd.DataFrame(schedules).to_sql('team_schedules', get_engine(), if_exists='replace', index=False)
        print("Schedule map successfully finalized.")

if __name__ == '__main__':
    run()
