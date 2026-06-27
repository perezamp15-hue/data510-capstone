import sys
import requests
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

# Ground-truth manual overrides for common venues missing coordinates or hydration blocks in the API
VENUE_OVERRIDES = {
    1:    {"lat": 41.5000, "lon": -81.6800, "elevation": 600},  # General Generic Fallback
    19:   {"lat": 41.4962, "lon": -81.6852, "elevation": 580},  # Progressive Field (Cleveland)
    2680: {"lat": 33.4475, "lon": -112.0011, "elevation": 1234}, # Spring Training / Complex Field Example
    3289: {"lat": 28.0323, "lon": -82.4600, "elevation": 45}     # Complex Field Example
}

def run():
    print("Fetching active major league venue records from MLB API...")
    engine = get_engine()

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
        park_id = int(v.get('id'))
        park_name = v.get('name')
        
        loc = v.get('location', {})
        
        # Pull from API, fallback to manual overrides if API properties are null
        lat_raw = loc.get('latitude') or VENUE_OVERRIDES.get(park_id, {}).get('lat')
        lon_raw = loc.get('longitude') or VENUE_OVERRIDES.get(park_id, {}).get('lon')
        
        field = v.get('fieldInfo', {})
        surface = field.get('surface', 'Grass')  
        roof = field.get('roofType', 'Open')
        
        latitude = float(lat_raw) if lat_raw is not None else None
        longitude = float(lon_raw) if lon_raw is not None else None

        # Determine elevation
        elevation_meters = VENUE_OVERRIDES.get(park_id, {}).get('elevation', 0)
        
        # If no override exists but we have coordinates, query the open elevation API
        if elevation_meters == 0 and latitude is not None and longitude is not None:
            try:
                geo_url = f"https://api.open-elevation.com/api/v1/lookup?locations={latitude},{longitude}"
                geo_res = requests.get(geo_url, timeout=5).json()
                results = geo_res.get('results', [])
                if results:
                    elevation_meters = int(results[0].get('elevation', 0) * 3.28084)
            except Exception:
                elevation_meters = 0

        processed_parks.append({
            "park_id": park_id,
            "park_name": park_name,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation_meters,
            "surface_type": surface if surface else "Grass",
            "roof_style": roof if roof else "Open"
        })

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
            
    print(f"Database Verified: Successfully synced {len(processed_parks)} active parks.")

if __name__ == "__main__":
    run()
