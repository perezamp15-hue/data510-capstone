import pandas as pd
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run():
    print("Scraping high-fidelity major league park dimensions...")
    
    # Hydrate location for lat/long coordinates, fieldInfo for surface/roof architectures
    url = "https://statsapi.mlb.com/api/v1/venues?sportId=1&hydrate=location,fieldInfo"
    
    try:
        data = fetch_api_json(url)
        venues = data.get('venues', [])
        
        parsed_parks = []
        for venue in venues:
            park_id = venue.get('id')
            name = venue.get('name')
            
            # 1. Coordinates Extraction
            loc_data = venue.get('location', {})
            coords = loc_data.get('defaultCoordinates', {})
            latitude = coords.get('latitude', None)
            longitude = coords.get('longitude', None)
            
            # Convert float coordinates to clean strings if they exist
            lat_str = str(latitude) if latitude is not None else None
            lon_str = str(longitude) if longitude is not None else None
            
            # 2. Structural/Field Architecture Attributes
            field_info = venue.get('fieldInfo', {})
            surface = field_info.get('surface', None)
            roof_type = field_info.get('roofType', None)
            
            # Note: MLB's API usually stores elevation inside specialized climate 
            # nested tracking dictionaries, default to None if missing on root fields
            elevation = field_info.get('elevation', None)
            if elevation is not None:
                elevation = str(elevation)
            
            parsed_parks.append({
                "park_id": park_id,
                "name": name,
                "latitude": lat_str,
                "longitude": lon_str,
                "elevation": elevation,
                "surface": surface,
                "roof_type": roof_type
            })
            
        df = pd.DataFrame(parsed_parks)
        if df.empty:
            print("No detailed venue records compiled.")
            return
            
        engine = get_engine()
        
        # Safe Upsert routing matching your precise schema matrix
        print(f"Upserting stadium profiles for {len(df)} records into Database...")
        with engine.begin() as conn:
            for _, row in df.iterrows():
                sql = text("""
                    INSERT INTO parks (park_id, name, latitude, longitude, elevation, surface, roof_type)
                    VALUES (:park_id, :name, :latitude, :longitude, :elevation, :surface, :roof_type)
                    ON CONFLICT (park_id) 
                    DO UPDATE SET 
                        name = EXCLUDED.name,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        elevation = EXCLUDED.elevation,
                        surface = EXCLUDED.surface,
                        roof_type = EXCLUDED.roof_type;
                """)
                conn.execute(sql, {
                    "park_id": int(row['park_id']),
                    "name": row['name'],
                    "latitude": row['latitude'],
                    "longitude": row['longitude'],
                    "elevation": row['elevation'],
                    "surface": row['surface'],
                    "roof_type": row['roof_type']
                })
                
        print("Successfully filled and aligned park dimension records!")
        
    except Exception as e:
        print(f"Failed to gather detailed stadium configurations: {e}")

if __name__ == '__main__':
    run()
