import sys
import re
import requests
from datetime import datetime
from sqlalchemy import text
from db_client import get_engine

def run(target_date):
    print(f"Loading Core Game Records for date context: {target_date}")
    engine = get_engine()
    
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={target_date}"
    dates = requests.get(url).json().get('dates', [])
    if not dates:
        print("No matches scheduled on this date window.")
        return

    with engine.begin() as conn:
        for date_node in dates:
            for g in date_node.get('games', []):
                game_pk = g['gamePk']
                status = g.get('status', {}).get('abstractGameState', '')
                if status != 'Final':
                    continue

                # Initialize defaults
                temp, sky, wind_spd, wind_direction = None, None, None, None
                hp_id, fb_id, sb_id, tb_id = None, None, None, None
                officials_list = []
                weather_string = None
                
                dh_flag = g.get('doubleHeader') in ['Y', 'S']

                # 1. Team-level Win Determinations
                teams = g.get('teams', {})
                home_team_id = teams.get('home', {}).get('team', {}).get('id')
                away_team_id = teams.get('away', {}).get('team', {}).get('id')
                home_score = teams.get('home', {}).get('score', 0)
                away_score = teams.get('away', {}).get('score', 0)
                
                is_home_team_win = home_score > away_score
                winning_team_id = home_team_id if is_home_team_win else away_team_id

                # 2. Extract Weather Payload and Officials from the Boxscore Endpoint
                box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                try:
                    box_res = requests.get(box_url)
                    if box_res.status_code == 200:
                        box_data = box_res.json()
                        officials_list = box_data.get('officials', [])
                        
                        # Loop through info array to find the Weather label
                        for item in box_data.get('info', []):
                            if item.get('label') == 'Weather':
                                weather_string = item.get('value')
                except Exception as e:
                    print(f"Boxscore check skipped for game {game_pk}: {e}")

                # 3. Production Weather String Split Engine
                if weather_string:
                    try:
                        # Parse Temperature
                        temp_match = re.search(r"(\d+)\s*degrees", weather_string, re.IGNORECASE)
                        temp = int(temp_match.group(1)) if temp_match else None

                        # Parse Sky Condition (split down the first comma, clip at the first period)
                        parts = weather_string.split(',', 1)
                        sky = parts[1].split('.')[0].strip() if len(parts) > 1 else "Unknown"

                        # Parse Wind Metrics safely without breaking on punctuation changes
                        weather_lower = weather_string.lower()
                        
                        if "roof closed" in weather_lower or "indoors" in weather_lower:
                            wind_spd = 0
                            wind_direction = "INDOORS"
                            sky = "INDOORS"
                        elif "mph" in weather_lower:
                            # Split string right down the middle at "mph"
                            left_side, right_side = weather_lower.split("mph", 1)
                            
                            # Grab the last numeric sequence to the left of "mph"
                            speed_digits = re.findall(r'\d+', left_side)
                            if speed_digits:
                                wind_spd = int(speed_digits[-1])
                            
                            # Clean up the trailing data vector to the right of "mph"
                            direction_clean = right_side.replace('.', '').replace(',', '').strip().upper()
                            wind_direction = direction_clean if direction_clean else "CALM"
                        else:
                            # Fallback for structural outliers
                            wind_spd = 0
                            wind_direction = "CALM"
                    except Exception as e:
                        print(f"Weather parser skipped row formatting on game {game_pk}: {e}")
                        wind_spd = 0
                        wind_direction = "UNKNOWN"
                else:
                    # Default values if API text data is completely null
                    wind_spd = 0
                    wind_direction = "CALM"

                # 4. Parse and Seed Game Officials
                for off in officials_list:
                    oid = off.get('official', {}).get('id')
                    oname = off.get('official', {}).get('fullName', 'Unknown Umpire')
                    role = off.get('officialType')
                    
                    if not oid:
                        continue
                    
                    conn.execute(text("INSERT INTO umpires (umpire_id, umpire_name) VALUES (:id, :name) ON CONFLICT (umpire_id) DO NOTHING;"), {"id": oid, "name": oname})
                    
                    if role == 'Home Plate': hp_id = oid
                    elif role == 'First Base': fb_id = oid
                    elif role == 'Second Base': sb_id = oid
                    elif role == 'Third Base': tb_id = oid

                start_time = g.get('gameDate')
                start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ") if start_time else None

                # 5. Populate Data Warehouse Fields
                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, season, game_type, scheduled_start, park_id, home_team_id, away_team_id,
                        home_score, away_score, winning_team_id, is_home_team_win, day_night_type, is_doubleheader,
                        temperature_f, sky_condition, wind_speed_mph, wind_direction, home_plate_ump_id, first_base_ump_id, second_base_ump_id, third_base_ump_id
                    ) VALUES (
                        :game_pk, :game_date, :season, :game_type, :start, :park, :home, :away, :h_score, :a_score, :win_team, :is_home_win, :dn, :dh,
                        :temp, :sky, :w_spd, :w_dir, :hp, :fb, :sb, :tb
                    ) ON CONFLICT (game_pk) DO UPDATE SET
                        home_score = EXCLUDED.home_score, 
                        away_score = EXCLUDED.away_score,
                        winning_team_id = EXCLUDED.winning_team_id,
                        is_home_team_win = EXCLUDED.is_home_team_win,
                        is_doubleheader = EXCLUDED.is_doubleheader,
                        temperature_f = EXCLUDED.temperature_f, 
                        sky_condition = EXCLUDED.sky_condition,
                        wind_speed_mph = EXCLUDED.wind_speed_mph,
                        wind_direction = EXCLUDED.wind_direction,
                        home_plate_ump_id = EXCLUDED.home_plate_ump_id,
                        first_base_ump_id = EXCLUDED.first_base_ump_id,
                        second_base_ump_id = EXCLUDED.second_base_ump_id,
                        third_base_ump_id = EXCLUDED.third_base_ump_id;
                """), {
                    "game_pk": game_pk, "game_date": datetime.strptime(target_date, "%Y-%m-%d").date(), "season": g.get('season', 2023),
                    "game_type": g.get('gameType', 'R'), "start": start_dt, "park": g.get('venue', {}).get('id'),
                    "home": home_team_id, "away": away_team_id, "h_score": home_score, "a_score": away_score,
                    "win_team": winning_team_id, "is_home_win": is_home_team_win, "dn": g.get('dayNight'), "dh": dh_flag,
                    "temp": temp, "sky": sky, "w_spd": wind_spd, "w_dir": wind_direction, "hp": hp_id, "fb": fb_id, "sb": sb_id, "tb": tb_id
                })
    print(f"Core games mapping entries finalized for date window: {target_date}")
