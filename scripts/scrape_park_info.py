import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Scraping detailed major league park dimensions...")
    url = "https://statsapi.mlb.com/api/v1/venues?sportId=1&hydrate=location,fieldInfo"
    try:
        data = fetch_api_json(url)
        venues = data.get('venues', [])
        parsed = []
        
        for v in venues:
            loc = v.get('location', {}).get('defaultCoordinates', {})
            f_info = v.get('fieldInfo', {})
            
            # Typecasting safely
            lat = loc.get('latitude')
            lon = loc.get('longitude')
            elev = f_info.get('elevation')
            
            parsed.append({
                "park_id": int(v.get('id')),
                "park_name": v.get('name'),
                "latitude": float(lat) if lat is not None else None,
                "longitude": float(lon) if lon is not None else None,
                "elevation": int(elev) if elev is not None else None,
                "surface_type": f_info.get('surface'),
                "roof_style": f_info.get('roofType')
            })
            
        df = pd.DataFrame(parsed)
        engine = get_engine()
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO parks (park_id, park_name, latitude, longitude, elevation, surface_type, roof_style)
                    VALUES (:park_id, :park_name, :latitude, :longitude, :elevation, :surface_type, :roof_style)
                    ON CONFLICT (park_id) DO UPDATE SET 
                        park_name = EXCLUDED.park_name, latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
                        elevation = EXCLUDED.elevation, surface_type = EXCLUDED.surface_type, roof_style = EXCLUDED.roof_style;
                """), row.to_dict())
        print(f"Successfully processed {len(df)} stadium dimensions.")
    except Exception as e:
        print(f"Failed to gather ballpark configurations: {e}")
