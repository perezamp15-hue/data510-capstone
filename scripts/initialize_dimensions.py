import sys
import requests
from sqlalchemy import text
from db_client import get_engine

def seed_static_dimensions():
    print("Initializing Master Data Warehousing Dimensions with 2026 Registry...")
    engine = get_engine()

    # 🏔️ Exact 2026 Live MLB API ID-to-Elevation Mapping Matrix
    ELEVATION_REGISTRY = {
        1: 54,       # Angel Stadium
        2: 30,       # Oriole Park at Camden Yards
        3: 20,       # Fenway Park
        4: 25,       # Guaranteed Rate Field
        5: 12,       # Progressive Field
        7: 521,      # Kauffman Stadium
        12: 10,      # Tropicana Field (Near Sea Level)
        14: 11,      # Rogers Centre
        15: 1086,    # Chase Field (Phoenix Desert elevation)
        17: 510,     # Wrigley Field
        19: 5280,    # Coors Field (Mile High - 5,280 ft!)
        22: 261,     # Dodger Stadium
        31: 25,      # PNC Park
        32: 615,     # American Family Field (Milwaukee)
        680: 10,     # T-Mobile Park
        2392: 41,    # Daikin Park (Formerly Minute Maid Park - Houston)
        2394: 595,   # Comerica Park
        2395: 20,    # Oracle Park
        2602: 600,   # Great American Ball Park
        2680: 25,    # Petco Park
        2681: 15,    # Citizens Bank Park
        2889: 604,   # Busch Stadium
        3289: 30,    # Citi Field
        3309: 35,    # Nationals Park
        3312: 582,   # Target Field
        3313: 9,     # Yankee Stadium
        4169: 15,    # loanDepot park (Miami)
        4705: 1050,  # Truist Park (Atlanta)
        5325: 585,   # Globe Life Field (Arlington)
        5340: 7350,  # Estadio Alfredo Harp Helu (Mexico City)
        
        # --- Spring Training / Alternate Defaults (generic baselines) ---
        2500: 1150,  # Tempe Diablo Stadium
        2507: 1240,  # Hohokam Stadium
        2508: 31,    # Ed Smith Stadium
        2511: 177,   # Joker Marchant Stadium
        2518: 1100,  # American Family Fields of Phoenix
        2520: 15,    # Roger Dean Chevrolet Stadium
        2523: 42,    # George M. Steinbrenner Field
        2526: 17,    # LECOM Park
        2529: 25,    # Sutter Health Park (Sacramento)
        2530: 1140,  # Peoria Stadium
        2532: 1210,  # Scottsdale Stadium
        2534: 8,     # Charlotte Sports Park
        2536: 12,    # TD Ballpark
        2603: 1170,  # Surprise Stadium
        2700: 30,    # BayCare Ballpark
        3809: 1110,  # Camelback Ranch
        3834: 980,   # Goodyear Ballpark
        4249: 1100,  # Salt River Fields
        4309: 14,    # JetBlue Park
        4629: 1240,  # Sloan Park
        5000: 15,    # CACTI Park of the Palm Beaches
        5355: 3000,  # Las Vegas Ballpark
        5380: 12,    # CoolToday Park
        5445: 890,   # Field of Dreams
    }

    with engine.begin() as conn:
        print("Syncing master park profiles with corrected 2026 elevation map...")
        url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
        venues = requests.get(url).json().get('venues', [])
        
        for v in venues:
            park_id = v['id']
            park_name = v['name']
            
            # Grabs exact elevation; defaults safely to a baseline 500 if an unlisted minor node appears
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
            
    print("Public dimensions synchronization complete.")

if __name__ == "__main__":
    seed_static_dimensions()
