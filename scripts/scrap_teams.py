import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Caching all Major League teams...")
    url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
    try:
        data = fetch_api_json(url)
        teams_list = data.get('teams', [])
        parsed_teams = []
        
        for t in teams_list:
            # Only pull major league clubs
            if t.get('sport', {}).get('id') != 1:
                continue
            parsed_teams.append({
                "team_id": t.get('id'),
                "abbreviation": t.get('fileCode', '').upper() or t.get('abbreviation'),
                "team_name": t.get('name'),
                "city": t.get('locationName'),
                "nickname": t.get('teamName'),
                "league": t.get('league', {}).get('name', 'AL' if 'American' in t.get('league', {}).get('name', '') else 'NL')[:2].upper(),
                "division": t.get('division', {}).get('name', '').split(' ')[-1]
            })
            
        df = pd.DataFrame(parsed_teams)
        engine = get_engine()
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO teams (team_id, abbreviation, team_name, city, nickname, league, division)
                    VALUES (:team_id, :abbreviation, :team_name, :city, :nickname, :league, :division)
                    ON CONFLICT (team_id) DO UPDATE SET 
                        abbreviation = EXCLUDED.abbreviation, team_name = EXCLUDED.team_name,
                        city = EXCLUDED.city, nickname = EXCLUDED.nickname, league = EXCLUDED.league, division = EXCLUDED.division;
                """), row.to_dict())
        print(f"Successfully tracked {len(df)} teams.")
    except Exception as e:
        print(f"Failed to track team metadata mapping matrix: {e}")
