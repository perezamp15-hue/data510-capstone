import requests
from sqlalchemy import text
from db_client import get_engine

def run():
    print("Scraping master MLB team profiles...")
    engine = get_engine()
    
    url = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
    teams = requests.get(url).json().get('teams', [])
    
    if not teams:
        print("No team data returned from API.")
        return

    with engine.begin() as conn:
        # Base table initialization
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.teams (
                team_id integer NOT NULL PRIMARY KEY,
                team_name text NOT NULL
            );
        """))
        
        # Self-Healing Migration: Explicitly patch missing schema columns if table already existed
        conn.execute(text("ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS team_code varchar(10);"))
        conn.execute(text("ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS abbreviation varchar(10);"))
        conn.execute(text("ALTER TABLE public.teams ADD COLUMN IF NOT EXISTS location_name text;"))

        for t in teams:
            conn.execute(text("""
                INSERT INTO public.teams (team_id, team_name, team_code, abbreviation, location_name)
                VALUES (:id, :name, :code, :abbr, :loc)
                ON CONFLICT (team_id) DO UPDATE SET
                    team_name = EXCLUDED.team_name,
                    team_code = EXCLUDED.team_code,
                    abbreviation = EXCLUDED.abbreviation,
                    location_name = EXCLUDED.location_name;
            """), {
                "id": t['id'], 
                "name": t['name'], 
                "code": t.get('teamCode'),
                "abbr": t.get('abbreviation'), 
                "loc": t.get('locationName')
            })
    print(f"Cleanly synchronized {len(teams)} master team dimensions.")
