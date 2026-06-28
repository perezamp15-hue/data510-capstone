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

                # Initialize defaults matching public.games column types exactly
                temp, sky, wind_spd, wind_direction = None, None, None, None
                hp_id, fb_id, sb_id, tb_id = None, None, None, None
                officials_list = []
                weather_string = None
                
                # is_doubleheader boolean mapping
                dh_flag = g.get('doubleHeader') in ['Y', 'S']

                # 1. Analytical Win & Indicator Evaluations
                teams = g.get('teams', {})
                home_team_id = teams.get('home', {}).get('team', {}).get('id')
                away_team_id = teams.get('away', {}).get('team', {}).get('id')
                home_score = teams.get('home', {}).get('score', 0)
                away_score = teams.get('away', {}).get('score', 0)
                
                is_home_team_win = home_score > away_score
                winning_team_id = home_team_id if is_home_team_win else away_team_id

                # 2. Tier 1: Extract Weather Payload & Roster from Boxscore Endpoint
                box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                try:
                    box_res = requests.get(box_url)
                    if box_res.status_code == 200:
                        box_data = box_res.json()
                        officials_list = box_data.get('officials', [])
                        
                        for item in box_data.get('info', []):
                            if item.get('label') == 'Weather':
                                weather_string = item.get('value')
                except:
                    pass

                # 3. Tier 2 Fallback: If weather_string is blank, parse feed/live historical gameData
                if not weather_string or "mph" not in weather_string.lower():
                    try:
                        live_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
                        live_res = requests.get(live_url)
                        if live_res.status_code == 200:
                            live_data = live_res.json()
                            
                            if not officials_list:
                                officials_list = live_data.get('liveData', {}).get('boxscore', {}).get('officials', [])
                            
                            weather_block = live_data.get('gameData', {}).get('weather', {})
                            if weather_block.get('wind'):
                                raw_w_spd = weather_block.get('temp', '')
                                raw_cond = weather_block.get('condition', '')
                                raw_wind = weather_block.get('wind', '')
                                weather_string = f"{raw_w_spd} degrees, {raw_cond}. Wind {raw_wind}"
                            else:
                                for item in live_data.get('liveData', {}).get('boxscore', {}).get('info', []):
                                    if item.get('label') == 'Weather':
                                        weather_string = item.get('value')
                    except:
                        pass

                # 4. Substring Weather Extraction Split Engine
                if weather_string:
                    try:
                        # Parse Temperature
                        temp_match = re.search(r"(\d+)\s*degrees", weather_string, re.IGNORECASE)
                        temp = int(temp_match.group(1)) if temp_match else None

                        # Parse Sky Condition
                        parts = weather_string.split(',', 1)
                        sky = parts[1].split('.')[0].strip() if len(parts) > 1 else "Unknown"

                        weather_lower = weather_string.lower()
                        
                        if "roof closed" in weather_lower or "indoors" in weather_lower:
                            wind_spd = 0
                            wind_direction = "INDOORS"
                            sky = "INDOORS"
                        elif "mph" in weather_lower:
                            left_side, right_side = weather_lower.split("mph", 1)
                            
                            speed_digits = re.findall(r'\d+', left_side)
                            if speed_digits:
                                wind_spd = int(speed_digits[-1])
                            
                            direction_clean = right_side.replace('.', '').replace(',', '').strip().upper()
                            wind_direction = direction_clean if direction_clean else "CALM"
                        else:
                            speed_digits = re.findall(r'\d+', weather_lower)
                            if speed_digits and len(speed_digits) > 1:
                                wind_spd = int(speed_digits[-1])
                                wind_direction = "UNKNOWN"
                            else:
                                wind_spd = 0
                                wind_direction = "CALM"
                    except Exception as e:
                        print(f"Weather parser skipped row formatting on game {game_pk}: {e}")
                        wind_spd = 0
                        wind_direction = "UNKNOWN"
                else:
                    wind_spd = 0
                    wind_direction = "CALM"

                # 5. Parse and Seed Game Officials
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

                # 6. Populate public.games Warehouse Schema
                conn.execute(text("""
                    INSERT INTO public.games (
                        game_pk, game_date, season, game_type, scheduled_start, park_id, home_team_id, away_team_id,
                        home_score, away_score, day_night_type, is_doubleheader, temperature_f, sky_condition, 
                        wind_speed_mph, wind_direction, home_plate_ump_id, first_base_ump_id, second_base_ump_id, 
                        third_base_ump_id, winning_team_id, is_home_team_win
                    ) VALUES (
                        :game_pk, :game_date, :season, :game_type, :start, :park, :home, :away, :h_score, :a_score, :dn, :dh,
                        :temp, :sky, :w_spd, :w_dir, :hp, :fb, :sb, :tb, :win_team, :is_home_win
                    ) ON CONFLICT (game_pk) DO UPDATE SET
                        home_score = EXCLUDED.home_score, 
                        away_score = EXCLUDED.away_score,
                        day_night_type = EXCLUDED.day_night_type,
                        is_doubleheader = EXCLUDED.is_doubleheader,
                        temperature_f = EXCLUDED.temperature_f, 
                        sky_condition = EXCLUDED.sky_condition,
                        wind_speed_mph = EXCLUDED.wind_speed_mph,
                        wind_direction = EXCLUDED.wind_direction,
                        home_plate_ump_id = EXCLUDED.home_plate_ump_id,
                        first_base_ump_id = EXCLUDED.first_base_ump_id,
                        second_base_ump_id = EXCLUDED.second_base_ump_id,
                        third_base_ump_id = EXCLUDED.third_base_ump_id,
                        winning_team_id = EXCLUDED.winning_team_id,
                        is_home_team_win = EXCLUDED.is_home_team_win;
                """), {
                    "game_pk": game_pk, "game_date": datetime.strptime(target_date, "%Y-%m-%d").date(), "season": g.get('season', 2023),
                    "game_type": g.get('gameType', 'R'), "start": start_dt, "park": g.get('venue', {}).get('id'),
                    "home": home_team_id, "away": away_team_id, "h_score": home_score, "a_score": away_score,
                    "dn": g.get('dayNight'), "dh": dh_flag, "temp": temp, "sky": sky, "w_spd": wind_spd, "w_dir": wind_direction, 
                    "hp": hp_id, "fb": fb_id, "sb": sb_id, "tb": tb_id, "win_team": winning_team_id, "is_home_win": is_home_team_win
                })
    print(f"Core games mapping entries finalized for date window: {target_date}")
