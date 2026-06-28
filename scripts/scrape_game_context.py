import sys
import requests
from sqlalchemy import text
from db_client import get_engine

def run(target_date):
    print(f"Running Consolidated Game Context Scraper for {target_date}...")
    engine = get_engine()
    
    with engine.connect() as conn:
        games = conn.execute(
            text("SELECT game_pk FROM games WHERE game_date = :date"), 
            {"date": target_date}
        ).fetchall()
        
    if not games:
        print(f"No games found in database for {target_date}.")
        return

    with engine.begin() as conn:
        for row in games:
            game_pk = row[0]
            try:
                url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                response = requests.get(url)
                if response.status_code != 200:
                    continue
                data = response.json()
                
                # --- Parse Weather Data ---
                info = data.get('info', [])
                weather_str = next((item['value'] for item in info if item['label'] == 'Weather'), None)
                if weather_str:
                    conn.execute(text("""
                        INSERT INTO game_weather (game_pk, weather_info)
                        VALUES (:game_pk, :weather)
                        ON CONFLICT (game_pk) DO UPDATE SET weather_info = EXCLUDED.weather_info;
                    """), {"game_pk": game_pk, "weather": weather_str})

                # --- Parse Umpire Data ---
                officials = data.get('officials', [])
                for off in officials:
                    official_id = off['official']['id']
                    name = off['official']['fullName']
                    role = off['officialType']
                    
                    conn.execute(text("""
                        INSERT INTO umpires (umpire_id, name)
                        VALUES (:id, :name) ON CONFLICT (umpire_id) DO NOTHING;
                    """), {"id": official_id, "name": name})
                    
                    conn.execute(text("""
                        INSERT INTO game_umpires (game_pk, umpire_id, position)
                        VALUES (:game_pk, :id, :role) ON CONFLICT (game_pk, umpire_id) DO NOTHING;
                    """), {"game_pk": game_pk, "id": official_id, "role": role})

                # --- Parse Defensive Alignments (Saved!) ---
                teams_data = data.get('teams', {})
                for team_type in ['home', 'away']:
                    team_info = teams_data.get(team_type, {})
                    team_id = team_info.get('team', {}).get('id')
                    players = team_info.get('players', {})
                    
                    for player_key, player_val in players.items():
                        player_id = player_val.get('person', {}).get('id')
                        position = player_val.get('position', {})
                        
                        # Filter out benchwarmers or DH roles (keep active defenders 1-9)
                        if position and position.get('code') not in ['D', '10', '11', 'Y']:
                            try:
                                pos_id = int(position.get('code'))
                                conn.execute(text("""
                                    INSERT INTO defensive_alignments (game_pk, player_id, position_id, team_id)
                                    VALUES (:game_pk, :player_id, :pos_id, :team_id)
                                    ON CONFLICT (game_pk, player_id, position_id) DO NOTHING;
                                """), {
                                    "game_pk": game_pk, "player_id": player_id, 
                                    "pos_id": pos_id, "team_id": team_id
                                })
                            except ValueError:
                                continue

            except Exception as e:
                print(f"Failed to parse context details for game {game_pk}: {e}")
                
    print(f"Consolidated game data processing finished for {target_date}.")
