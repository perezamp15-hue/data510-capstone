import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Scraping detailed major league park dimensions via hydrations...")
    # Hydrating the venues node directly through the active sports endpoint ensures fieldInfo populates
    url = "https://statsapi.mlb.com/api/v1/venues?sportId=1&hydrate=fieldInfo,location"
    try:
        data = fetch_api_json(url)
        venues = data.get('venues', [])
        parsed = []
        
        for v in venues:
            loc = v.get('location', {}).get('defaultCoordinates', {})
            # CRITICAL PAYLOAD FIX: The API uses 'fieldInfo', verify nesting paths
            f_info = v.get('fieldInfo', {}) or {}
            
            parsed.append({
                "park_id": int(v.get('id')), 
                "park_name": v.get('name'),
                "latitude": float(loc.get('latitude')) if loc.get('latitude') else None,
                "longitude": float(loc.get('longitude')) if loc.get('longitude') else None,
                "elevation": int(f_info.get('elevation')) if f_info.get('elevation') else None,
                "surface_type": f_info.get('surface'), 
                "roof_style": f_info.get('roofType') # Check your DB column maps to 'roofType' string
            })
            
        df = pd.DataFrame(parsed)
        if df.empty: return
        
        engine = get_engine()
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO parks (park_id, park_name, latitude, longitude, elevation, surface_type, roof_style)
                    VALUES (:park_id, :park_name, :latitude, :longitude, :elevation, :surface_type, :roof_style)
                    ON CONFLICT (park_id) DO UPDATE SET 
                        elevation = EXCLUDED.elevation, 
                        surface_type = EXCLUDED.surface_type, 
                        roof_style = EXCLUDED.roof_style;
                """), row.to_dict())
        print("Venues and stadium properties updated successfully.")
    except Exception as e:
        print(f"Parks Error: {e}")

if __name__ == "__main__": run()
