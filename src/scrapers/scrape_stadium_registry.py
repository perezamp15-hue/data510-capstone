from datetime import date

# Fetch the actual calendar year automatically at runtime
CURRENT_YEAR = date.today().year 

# Example modifying the Stadium Registry script from earlier:
def fetch_mlb_stadiums(season: int = CURRENT_YEAR):
    """
    Queries the MLB Venue Registry. 
    Defaults to the absolute current calendar year automatically.
    """
    url = f"https://statsapi.mlb.com/api/v1/venues?sportId=1&season={season}"
    response = requests.get(url)
    # ... rest of your code stays exactly the same
