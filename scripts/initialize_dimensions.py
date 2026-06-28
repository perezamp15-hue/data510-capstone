import sys
import requests
from sqlalchemy import text
from db_client import get_engine
import scripts.scrape_teams as scrape_teams
import scripts.scrape_players as scrape_players

def seed_static_dimensions():
    print("Running Master Data Warehouse Dimension Suite...")
    engine = get_engine()

    # Exact 2026 Live MLB API ID-to-Elevation Mapping Matrix
    ELEVATION_REGISTRY = {
        1: 54, 2: 30, 3: 20, 4: 25, 5: 12, 7: 521, 12: 10, 14: 11, 15: 1086,
        17: 510, 19: 5280, 22: 261, 31: 25, 32: 615, 680: 10, 2392: 41, 
        2394: 595, 2395: 20, 2602: 600, 2680: 25, 2681: 15, 2889: 604, 
        3289: 30, 3309: 35, 3312: 582, 3313: 9, 4169: 15, 4705: 1050, 
        5325: 585, 5340: 7350, 2500: 1150, 2507: 1240, 2508: 31, 2511: 177, 
        2518: 1100, 2520: 15, 2523: 42, 2526: 17, 2529: 25, 2530: 1140, 
        2532: 1210, 2534: 8, 2536: 12, 2603: 1170, 2700: 30, 3809: 1110, 
        3834: 980, 4249: 1100, 4309: 14, 4629: 1240, 5000: 15, 5355: 3000, 
        5380: 12, 5445: 890
    }

    with engine.begin() as conn:
        print("Syncing master park profiles with corrected 2026 elevation map...")
        url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
        venues = requests.get(url).json().get('venues', [])
        
        for v in venues:
            park_id = v['id']
            # Safeguard: Force character limit bounds to match character varying(150)
            park_name = v.get('name', 'Unknown Park')[:150]
            elevation = ELEVATION_REGISTRY.get(park_id, 500)

            conn.execute(text("""
                INSERT INTO public.parks (park_id, park_name, elevation)
                VALUES (:id, :name, :elevation)
                ON CONFLICT (park_id) DO UPDATE SET
                    park_name = EXCLUDED.park_name,
                    elevation = EXCLUDED.elevation;
            """), {
                "id": park_id, 
                "name": park_name, 
                "elevation": elevation
            })
            
    print("Park profile dimension initialization complete.")

    # Execute downstreamStandalone dimension loaders to avoid incomplete placeholders
    scrape_teams.run()

    for year in [2023, 2024, 2025, 2026]:
        scrape_players.run(year)

    print("All static master data dimensions fully configured!")

if __name__ == "__main__":
    seed_static_dimensions()
