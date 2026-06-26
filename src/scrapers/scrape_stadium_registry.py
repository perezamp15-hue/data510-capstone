import requests

def fetch_mlb_stadiums(season: int = 2026):
    """
    Queries the MLB StatsAPI global venue registry to scrape structural 
    information, canonical names, and geospatial coordinates for active stadiums.
    """
    # MLB Venues endpoint filtered for Major League sports profiles
    url = f"https://statsapi.mlb.com/api/v1/venues?sportId=1&season={season}"
    response = requests.get(url)
    
    stadiums_list = []
    
    if response.status_code != 200:
        print(f"Error communicating with MLB Venue Registry endpoint.")
        return stadiums_list
        
    data = response.json()
    venues = data.get("venues", [])
    
    for venue in venues:
        venue_id = venue.get("id")
        
        # We perform a deeper hydration step on the unique venue ID to extract 
        # precise geospatial coordinates and structural descriptors
        details_url = f"https://statsapi.mlb.com/api/v1/venues/{venue_id}"
        details_res = requests.get(details_url)
        
        # Standard safety structural defaults
        lat, lon = None, None
        city, state, country = None, None, None
        tz_offset = None
        
        if details_res.status_code == 200:
            v_data = details_res.json().get("venues", [{}])[0]
            
            # Extract high-precision latitude/longitude maps
            coords = v_data.get("location", {})
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            
            # Extract geographic placement metadata
            city = coords.get("city")
            state = coords.get("state")
            country = coords.get("country")
            
            # Extract time zone metadata (extremely useful for calculating sleep profiles!)
            tz_offset = v_data.get("timeZone", {}).get("offset")
            
        stadium_payload = {
            "venue_id": venue_id,
            "stadium_name": venue.get("name"),
            "city": city,
            "state": state,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "timezone_offset": tz_offset
        }
        
        stadiums_list.append(stadium_payload)
        
    return stadiums_list
