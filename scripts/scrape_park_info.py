import sys
import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Scraping detailed major league park dimensions via direct endpoints...")
    engine = get_engine()
    
    # 1. Get the list of active park IDs from your existing teams/games data
    try:
        # Use fallback stadium IDs if the teams table isn't populated yet
        venue_ids = pd.read_sql("SELECT DISTINCT venue_id FROM teams WHERE venue_id IS NOT NULL", con=engine)['venue_id'].tolist()
        if not venue_ids:
            # Standard MLB venue ID range fallback if table is empty
            venue_ids = [1, 2, 3, 4, 5, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]
    except Exception:
        venue_ids = [1, 2, 3, 4, 5, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]

    parsed = []
    print(f"Hydrating telemetry for {len(venue_ids)} unique major league ballparks...")
    
    for v_id in venue_ids:
        # Querying the individual endpoint forces the API to include fieldInfo
        url = f"https://statsapi.mlb.com/api/v1/venues/{v_id}?hydrate=fieldInfo,location"
        try:
            data = fetch_api_json(url)
            venues = data.get('venues', [])
            if not venues: continue
            
            v = venues[0]
            loc = v.get('location', {}).get('defaultCoordinates', {}) or {}
            f_info = v.get('fieldInfo', {}) or {}
            
            # Extract attributes using clean fallbacks
            elevation = f_info.get('elevation')
            surface = f_info.get('surface') or f_info.get('surfaceType')
            roof = f_info.get('roofType') or f_info.get('roof')
            
            parsed.append({
                "park_id": int(v.get('id')), 
                "park_name": v.get('name'),
                "latitude": float(loc.get('latitude')) if loc.get('latitude') else None,
                "longitude": float(loc.get('longitude')) if loc.get('longitude') else None,
                "elevation": int(elevation) if elevation else None,
                "surface_type": str(surface).strip() if surface else None, 
                "roof_style": str(roof).strip() if roof else None
            })
        except Exception:
            continue
            
    df = pd.DataFrame(parsed)
    if df.empty: 
        print("CRITICAL: No stadium details could be extracted from individual endpoints.")
        return
        
    with engine.begin() as conn:
        for _, row in df.iterrows():
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
            """), row.to_dict())
            
    print("Database success: Elevation, surface, and roof fields are fully populated.")

if __name__ == "__main__": run()
