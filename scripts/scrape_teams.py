import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Gathering master professional franchise dimensions...")
    url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
    try:
        data = fetch_api_json(url)
        raw_teams = data.get('teams', [])
        parsed = []
        
        for t in raw_teams:
            # FIX: Fallback automatically if sport id mapping block is missing from nested item
            sport_id = t.get('sport', {}).get('id')
            if sport_id is not None and sport_id != 1: 
                continue
                
            parsed.append({
                "team_id": int(t.get('id')),
                "abbreviation": t.get('fileCode', '').upper() or t.get('abbreviation', 'MLB'),
                "team_name": t.get('name'),
                "city": t.get('locationName'),
                "nickname": t.get('teamName'),
                "league": t.get('league', {}).get('name', 'AL')[:2].upper(),
                "division": t.get('division', {}).get('name', 'Unknown').split(' ')[-1]
            })
            
        df = pd.DataFrame(parsed)
        if df.empty: 
            print("API Warning: Zero active teams extracted.")
            return
            
        engine = get_engine()
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO teams (team_id, abbreviation, team_name, city, nickname, league, division)
                    VALUES (:team_id, :abbreviation, :team_name, :city, :nickname, :league, :division)
                    ON CONFLICT (team_id) DO UPDATE SET 
                        abbreviation = EXCLUDED.abbreviation, 
                        team_name = EXCLUDED.team_name, 
                        city = EXCLUDED.city, 
                        nickname = EXCLUDED.nickname, 
                        league = EXCLUDED.league, 
                        division = EXCLUDED.division;
                """), row.to_dict())
                
        print(f"Database Verified: Successfully synced {len(parsed)} team profiles.")
    except Exception as e: 
        print(f"Teams Error: {e}")

if __name__ == "__main__": 
    run()
