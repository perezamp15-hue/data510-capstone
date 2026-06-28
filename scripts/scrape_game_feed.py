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
    if not dates: return

    with engine.begin() as conn:
        for date_node in dates:
            for g in date_node.get('games', []):
                game_pk = g['gamePk']
                if g.get('status', {}).get('abstractGameState', '') != 'Final': continue

                temp, sky, wind_spd, wind_direction = None, None, None, None
                hp_id, fb_id, sb_id, tb_id = None, None, None, None
                officials_list = []
                dh_flag = g.get('doubleHeader') in ['Y', 'S']

                teams = g.get('teams', {})
                home_team_id = teams.get('home', {}).get('team', {}).get('id')
                away_team_id = teams.get('away', {}).get('team', {}).get('id')
                home_score = teams.get('home', {}).get('score', 0)
                away_score = teams.get('away', {}).get('score', 0)
                
                is_home_team_win = home_score > away_score
                winning_team_id = home_team_id if is_home_team_win else away_team_id

                try:
                    box_res = requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore")
                    if box_res.status_code == 200: officials_list = box_res.json().get('officials', [])
                except: pass

                try:
                    live_res = requests.get(f"http://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live")
                    if live_res.status_code == 200:
                        live_data = live_res.json()
                        if not officials_list: officials_list = live_data.get('liveData', {}).get('boxscore', {}).get('officials', [])
                        
                        weather_block = live_data.get('gameData', {}).get('weather', {})
                        raw_temp = weather_block.get('temp')
                        temp = int(raw_temp) if raw_temp else None
                        sky = weather_block.get('condition')
                        wind_raw = weather_block.get('wind')
                        
                        wind_spd = 0
                        wind_direction = "CALM"
                        
                        if wind_raw:
                            wind_lower = wind_raw.lower()
                            if "roof closed" in wind_lower or "indoors" in wind_lower:
                                wind_spd, wind_direction, sky = 0, "INDOORS", "INDOORS"
                            elif "mph" in wind_lower:
                                left_side, right_side = wind_lower.split("mph", 1)
                                speed_digits = re.findall(r'\d+', left_side)
                                if speed_digits: wind_spd = int(speed_digits[-1])
                                direction_clean = right_side.replace('.', '').replace(',', '').strip().upper()
                                wind_direction = direction_clean if direction_clean else "CALM"
                except Exception as e:
                    print(f"Weather extraction skipped for game {game_pk}: {e}")
                    wind_spd, wind_direction = 0, "UNKNOWN"

                for off in officials_list:
                    oid = off.get('official', {}).get('id')
                    oname = off.get('official', {}).get('fullName', 'Unknown Umpire')
                    role = off.get('officialType')
                    if not oid: continue
                    
                    conn.execute(text("INSERT INTO umpires (umpire_id, umpire_name) VALUES (:id, :name) ON CONFLICT (umpire_id) DO NOTHING;"), {"id": oid, "name": oname})
                    if role == 'Home Plate': hp_id = oid
                    elif role == 'First Base': fb_id = oid
                    elif role == 'Second Base': sb_id = oid
                    elif role == 'Third Base': tb_id = oid

                # Scoping checkpoint configuration
                start_time = g.get('gameDate')
                start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ") if start_time else None

                if g.get('venue', {}).get('id'):
                    venue_node = g.get('venue', {})
                    p_id = venue_node.get('id')
                    p_name = venue_node.get('name', f'Unknown Park (ID: {p_id})')
                    
                    park_exists = conn.execute(text("SELECT 1 FROM public.parks WHERE park_id = :id"), {"id": p_id}).fetchone()
                    if not park_exists:
                        try:
                            conn.execute(text("INSERT INTO public.parks (park_id, park_name, elevation) VALUES (:id, :name, 500) ON CONFLICT (park_id) DO NOTHING;"), {"id": p_id, "name": p_name})
                        except Exception as e: pass

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
                        home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score, day_night_type = EXCLUDED.day_night_type,
                        is_doubleheader = EXCLUDED.is_doubleheader, temperature_f = EXCLUDED.temperature_f, sky_condition = EXCLUDED.sky_condition,
                        wind_speed_mph = EXCLUDED.wind_speed_mph, wind_direction = EXCLUDED.wind_direction, home_plate_ump_id = EXCLUDED.home_plate_ump_id,
                        first_base_ump_id = EXCLUDED.first_base_ump_id, second_base_ump_id = EXCLUDED.second_base_ump_id, third_base_ump_id = EXCLUDED.third_base_ump_id,
                        winning_team_id = EXCLUDED.winning_team_id, is_home_team_win = EXCLUDED.is_home_team_win;
                """), {
                    "game_pk": game_pk, "game_date": datetime.strptime(target_date, "%Y-%m-%d").date(), "season": str(g.get('season', 2023)),
                    "game_type": g.get('gameType', 'R'), "start": start_dt, "park": g.get('venue', {}).get('id'),
                    "home": home_team_id, "away": away_team_id, "h_score": home_score, "a_score": away_score,
                    "dn": g.get('dayNight'), "dh": dh_flag, "temp": temp, "sky": sky, "w_spd": wind_spd, "w_dir": wind_direction, 
                    "hp": hp_id, "fb": fb_id, "sb": sb_id, "tb": tb_id, "win_team": winning_team_id, "is_home_win": is_home_team_win
                })
    print(f"Core games mapping entries finalized for date window: {target_date}")
