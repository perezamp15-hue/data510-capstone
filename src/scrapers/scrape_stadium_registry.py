import requests
from datetime import date

def fetch_mlb_stadiums(season: int = 2026):
    """
    Queries the MLB Venue Registry.
    Retrieves geospatial and environmental metadata for stadium mapping layers.
    """
    url = f"https://statsapi.mlb.com/api/v1/venues?sportId=1&season={season}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    stadiums = []

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            print(f"Failed to communicate with MLB Venue Registry (Status: {response.status_code})")
            return stadiums
    except requests.exceptions.RequestException as e:
        print(f"Connection timeout fetching stadium registry: {e}")
        return stadiums

    venues = response.json().get("venues", [])

    for venue in venues:
        venue_id = venue.get("id")
        if not venue_id:
            continue
            
        location = venue.get("location", {})
        coords = location.get("defaultCoordinates", {})
        
        # SAFEGUARD: Extract timezone offsets resiliently against inconsistent API casing
        tz_obj = venue.get("timeZone") or venue.get("timezone") or {}
        tz_offset = tz_obj.get("offset")
        
        try:
            latitude = float(coords.get("latitude")) if coords.get("latitude") else None
            longitude = float(coords.get("longitude")) if coords.get("longitude") else None
        except (ValueError, TypeError):
            latitude, longitude = None, None

        stadiums.append({
            "venue_id": int(venue_id),
            "stadium_name": venue.get("name"),
            "city": location.get("city"),
            "state": location.get("stateAbbrev") or location.get("state"),
            "country": location.get("country"),
            "latitude": latitude,
            "longitude": longitude,
            "timezone_offset": int(tz_offset) if tz_offset is not None else 0,
        })

    return stadiums
