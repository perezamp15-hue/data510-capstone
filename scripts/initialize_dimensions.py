import sys
import requests
from sqlalchemy import text
from db_client import get_engine

def run():
    print("Initializing Master Data Warehousing Dimensions...")
    engine = get_engine()

    with engine.begin() as conn:
        # 1. Venues / Parks Sync
        print("Synchronizing master park profiles with explicit structural telemetry...")
        url = "https://statsapi.mlb.com/api/v1/venues?sportId=1"
        venues = requests.get(url).json().get('venues', [])
        
        for v in venues:
            park_id = v['id']
            park_name = v['name']
            
            # Initialize defaults
            lat, lon, elev, surface, roof = None, None, None, None, None
            
            try:
                # Deep lookup for granular venue profiles
                detail_url = f"https://statsapi.mlb.com/api/v1/venues/{park_id}"
                res = requests.get(detail_url).json().get('venues', [{}])[0]
                
                # Maps directly to venues[i].location paths
                loc = res.get('location', {})
                lat = loc.get('latitude')
                lon = loc.get('longitude')
                elev = loc.get('elevation')
                
                # Maps directly to venues[i].fieldInfo paths
                field = res.get('fieldInfo', {})
                surface = field.get('turfType')  # Updated from surfaceType to turfType
                roof = field.get('roofType')
            except Exception as e:
                print(f"Telemetry lookup skipped for venue {park_id} ({park_name}): {e}")

            conn.execute(text("""
                INSERT INTO public.parks (park_id, park_name, latitude, longitude, elevation, surface_type, roof_style)
                VALUES (:id, :name, :lat, :lon, :elev, :surface, :roof)
                ON CONFLICT (park_id) DO UPDATE SET
                    park_name = EXCLUDED.park_name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    elevation = EXCLUDED.elevation,
                    surface_type = EXCLUDED.surface_type,
                    roof_style = EXCLUDED.roof_style;
            """), {
                "id": park_id, "name": park_name, "lat": lat, "lon": lon, 
                "elev": elev, "surface": surface, "roof": roof
            })
            
    print("Public dimensions synchronization complete.")

if __name__ == "__main__":
    run()
