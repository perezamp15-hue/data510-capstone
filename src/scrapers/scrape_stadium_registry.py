import requests
from datetime import date

CURRENT_YEAR = date.today().year

def fetch_mlb_stadiums(season: int = CURRENT_YEAR):
    """
    Queries the MLB Venue Registry.
    Defaults to the current MLB season.
    """
    url = f"https://statsapi.mlb.com/api/v1/venues?sportId=1&season={season}"

    response = requests.get(url)
    response.raise_for_status()

    venues = response.json().get("venues", [])

    stadiums = []

    for venue in venues:
        location = venue.get("location", {})

        stadiums.append({
            "venue_id": venue.get("id"),
            "stadium_name": venue.get("name"),
            "city": location.get("city"),
            "state": location.get("stateAbbrev"),
            "country": location.get("country"),
            "latitude": location.get("defaultCoordinates", {}).get("latitude"),
            "longitude": location.get("defaultCoordinates", {}).get("longitude"),
            "timezone_offset": venue.get("timeZone", {}).get("offset"),
        })

    return stadiums
