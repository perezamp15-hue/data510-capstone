# src/fetch_lineups.py
import requests
import psycopg2
from datetime import datetime
from config import DATABASE_URL

def fetch_and_store_daily_games():
    today_str = datetime.today().strftime('%Y-%m-%d')
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today_str}&hydrate=lineups,officials"
    
    response = requests.get(url).json()
    if "dates" not in response or len(response["dates"]) == 0:
        print(f"No matchups documented on {today_str}.")
        return

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    games = response["dates"][0]["games"]
    
    for game in games:
        game_id = game["gamePk"]
        home_team = game["teams"]["home"]["team"]["name"][:3].upper()
        away_team = game["teams"]["away"]["team"]["name"][:3].upper()
        stadium_id = game["venue"]["id"]
        
        # Determine Assigned Home Plate Official
        home_plate_ump = "Unknown"
        if "officials" in game:
            for official in game["officials"]:
                if official["officialType"]["description"] == "Home Plate Umpire":
                    home_plate_ump = official["official"]["fullName"]
        
        # Extract starting arrays
        home_lineup_ids, away_lineup_ids = [], []
        try:
            home_lineup_ids = [p["id"] for p in game["teams"]["home"]["lineup"]]
            away_lineup_ids = [p["id"] for p in game["teams"]["away"]["lineup"]]
        except KeyError:
            pass # Manager has not posted confirmed lineups yet

        cursor.execute("""
            INSERT INTO dim_games (game_id, game_date, home_team, away_team, stadium_id, home_lineup, away_lineup, umpire_home_plate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_id) 
            DO UPDATE SET home_lineup = EXCLUDED.home_lineup, away_lineup = EXCLUDED.away_lineup, umpire_home_plate = EXCLUDED.umpire_home_plate;
        """, (game_id, today_str, home_team, away_team, stadium_id, home_lineup_ids, away_lineup_ids, home_plate_ump))
        
    conn.commit()
    cursor.close()
    conn.close()
    print(f"Successfully tracked {len(games)} game structures for {today_str}.")

if __name__ == "__main__":
    fetch_and_store_daily_games()
