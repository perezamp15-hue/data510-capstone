import sys
import requests
import pandas as pd
import numpy as np
from db_client import get_engine
from sqlalchemy import text

def run(season=2026):
    print(f"Capturing active player profiles for {season}...")
    engine = get_engine()
    
    # Fetch 40-man active profiles over all major league clubs
    url = f"https://statsapi.mlb.com/api/v1/sports/1/players?season={season}"
    response = requests.get(url)
    response.raise_for_status()
    players_data = response.json().get("people", [])
    
    parsed_players = []
    for p in players_data:
        parsed_players.append({
            "player_id": int(p["id"]),
            "full_name": p["fullName"],
            "current_team_id": int(p.get("currentTeam", {}).get("id")) if p.get("currentTeam", {}).get("id") else None,
            "position_code": p.get("primaryPosition", {}).get("code"),
            "bats": p.get("batSide", {}).get("code"),
            "throws": p.get("pitchHand", {}).get("code"),
            "birth_date": p.get("birthDate"),
            "height": p.get("height"),
            "weight": int(p["weight"]) if p.get("weight") else None,
            "mlb_debut": p.get("mlbDebutDate"),
            "is_active": bool(p.get("active", True))
        })
        
    df = pd.DataFrame(parsed_players)
    if df.empty:
        print(f"No active player profiles returned for season {season}.")
        return

    # Clean up empty values so they map cleanly to SQL NULL
    df = df.replace({np.nan: None})

    try:
        print(f"Bulk loading {len(df)} players to remote staging table...")
        
        # Write pandas framework to temporary staging matrix
        df.to_sql("tmp_rosters_staging", con=engine, if_exists="replace", index=False)
        
        # Execute single server-side upsert logic block with explicit data type casts
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO players (
                    player_id, full_name, current_team_id, position_code, 
                    bats, throws, birth_date, height, weight, mlb_debut, is_active
                )
                SELECT 
                    CAST(player_id AS INTEGER), 
                    full_name, 
                    CAST(current_team_id AS INTEGER), 
                    position_code, 
                    bats, 
                    throws, 
                    CAST(birth_date AS DATE), 
                    height, 
                    CAST(weight AS INTEGER), 
                    CAST(mlb_debut AS DATE), 
                    CAST(is_active AS BOOLEAN)
                FROM tmp_rosters_staging
                ON CONFLICT (player_id) DO UPDATE SET 
                    full_name = EXCLUDED.full_name, 
                    current_team_id = EXCLUDED.current_team_id,
                    position_code = EXCLUDED.position_code, 
                    bats = EXCLUDED.bats, 
                    throws = EXCLUDED.throws, 
                    is_active = EXCLUDED.is_active;
            """))
            
            # Flush structural trace element files cleanly
            conn.execute(text("DROP TABLE IF EXISTS tmp_rosters_staging;"))
            
        print(f"Roster Matrix Sync finished: Successfully loaded {len(df)} players.")
        
    except Exception as e:
        print(f"Rosters Error for season {season}: {e}")

if __name__ == "__main__":
    passed_season = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    run(season=passed_season)