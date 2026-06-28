import sys
import requests
from sqlalchemy import text
from db_client import get_engine

def seed_static_dimensions():
    print("Initializing Master Data Warehousing Dimensions...")
    engine = get_engine()

    # Comprehensive Hardcoded MLB Stadium Elevation Registry (in feet)
    ELEVATION_REGISTRY = {
        10: 10,     # Shea Stadium (Historical context placeholder)
        11: 521,    # Kauffman Stadium (Royals)
        12: 582,    # Target Field (Twins)
        13: 20,     # Oracle Park (Giants)
        14: 16,     # Oakland Coliseum (Athletics)
        15: 11,     # Rogers Centre (Blue Jays)
        16: 604,    # Busch Stadium (Cardinals)
        17: 261,    # Dodger Stadium (Dodgers)
        18: 510,    # Wrigley Field (Cubs)
        19: 20,     # Fenway Park (Red Sox)
        21: 600,    # Great American Ball Park (Reds)
        22: 12,     # Progressive Field (Guardians)
        23: 54,     # Angel Stadium (Angels)
        26: 25,     # Guaranteed Rate Field (White Sox)
        27: 595,    # Comerica Park (Tigers)
        28: 1050,   # Truist Park (Braves)
        29: 9,      # Yankee Stadium (Yankees)
        31: 15,     # Citizens Bank Park (Phillies)
        32: 25,     # PNC Park (Pirates)
        33: 615,    # American Family Field (Brewers)
        34: 40,     # Busch Stadium II / Alternative Venue Node
        45: 35,     # Nationals Park (Nationals)
        2680: 25,   # Petco Park (Padres)
        2889: 30,   # Citi Field (Mets)
        3101: 585,  # Globe Life Field (Rangers)
        3289: 15,   # LoanDepot Park (Marlins)
        3954: 5280, # Coors Field (Rockies)
        4158: 1086, # Chase Field (D-Backs)
        4705: 41,   # Minute Maid Park (Astros)
    }

    with engine.begin() as conn:
        print("Synchronizing master park profiles with hardcoded elevations...")
        url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
        venues = requests.get(url).json().get('venues', [])
        
        for v in venues:
            park_id = v['id']
            park_name = v['name']
            
            # Lookup the park's permanent elevation; default to 0 if an obscure minor league site appears
            elevation = ELEVATION_REGISTRY.get(park_id, 0)

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
            
    print("Public dimensions synchronization complete.")

if __name__ == "__main__":
    seed_static_dimensions()
