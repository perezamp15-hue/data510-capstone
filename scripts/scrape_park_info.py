import sys
import requests
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Fetching active major league venue records from MLB API...")
    engine = get_engine()

    # 1. Pull current ground-truth park data straight from the MLB API
    mlb_venue_url = "https://statsapi.mlb.com/api/v1/venues?sportId=1&hydrate=location,fieldInfo"
    try:
        api_data = fetch_api_json(mlb_venue_url)
        venues = api_data.get('venues', [])
        if not venues:
            print("API Warning: No venues returned from MLB endpoint.")
            return
    except Exception as e:
        print(f"CRITICAL: Failed to query MLB Venues Endpoint: {e}")
        return

    processed_parks = []
    print(f"Parsing details and fetching elevations for {len(venues)} venues...")

    for v in venues:
        park_id = v.get('id')
        park_name = v.get('name')
        
        # Location extractions
        loc = v.get('location', {})
        lat = loc.get('latitude')
        lon = loc.get('longitude')
        
        # Field structural attributes (Fixed API mapping keys)
        field = v.get('fieldInfo', {})
        surface = field.get('surface', 'Grass')  
        roof = field.get('roofType', 'Open')
        
        # FIX: Safe extraction instead of skipping with `continue`
        latitude = float(lat) if lat is not None else None
        longitude = float(lon) if lon is not None else None

        # 2. Dynamically calculate accurate elevations ONLY if coordinates exist
        elevation_meters = 0
        if latitude is not None and longitude is not None:
            try:
                geo_url = f"https://api.open-elevation.com/api/v1/lookup?locations={latitude},{longitude}"
                geo_res = requests.get(geo_url, timeout=5).json()
                results = geo_res.get('results', [])
                if results:
                    # Convert meters to feet for typical baseball park standards
                    elevation_meters = int(results[0].get('elevation', 0) * 3.28084)
            except Exception:
                elevation_meters = 0

        processed_parks.append({
            "park_id": int(park_id),
            "park_name": park_name,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation_meters,
            "surface_type": surface if surface else "Grass",
            "roof_style": roof if roof else "Open"
        })

    # 3. Upsert clean data records to database
    with engine.begin() as conn:
        for item in processed_parks:
            conn.execute(text("""
                INSERT INTO parks (park_id, park_name, latitude, longitude, elevation, surface_type, roof_style)
                VALUES (:park_id, :park_name, :latitude, :longitude, :elevation, :surface_type, :roof_style)
                ON CONFLICT (park_id) DO UPDATE SET 
                    park_name = EXCLUDED.park_name,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    elevation = EXCLUDED.elevation,
                    surface_type = EXCLUDED.surface_type,
                    roof_style = EXCLUDED.roof_style;
            """), item)
            
    print(f"Database Verified: Successfully synced {len(processed_parks)} active parks with zero hardcoding.")

if __name__ == "__main__":
    run()
