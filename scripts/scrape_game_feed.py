import sys
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
                win_id, lose_id, save_id = None, None, None
                officials_list = []
                
                # Check for Doubleheaders properly ('Y' or 'S' mean it's part of a DH)
                dh_flag = g.get('doubleHeader') in ['Y', 'S']

                # Try standard boxscore endpoint for weather matrices
                box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                box_res = requests.get(box_url)
                
                if box_res.status_code == 200:
                    box_data = box_res.json()
                    officials_list = box_data.get('officials', [])
                    
                    info_list = box_data.get('info', [])
                    weather_node = next((i for i in info_list if i.get('label') == 'Weather'), None)
                    weather_str = weather_node.get('value', '') if weather_node else ''
                    
                    if weather_str:
                        try:
                            parts = weather_str.split(',')
                            if len(parts) >= 1:
                                temp = int(''.join(filter(str.isdigit, parts[0])))
                            if len(parts) >= 2:
                                sub_parts = parts[1].split('.')
                                sky = sub_parts[0].replace('Sky', '').strip()
                                wind_segment = next((p for p in parts if 'Wind' in p or 'wind' in p), '')
                                if not wind_segment and len(sub_parts) > 1:
                                    wind_segment = next((p for p in sub_parts if 'Wind' in p or 'wind' in p), '')
                                if wind_segment:
                                    wind_clean = wind_segment.lower().replace('wind', '').replace('mph', '').strip()
                                    wind_spd = int(''.join(filter(str.isdigit, wind_clean.split()[0])))
                                    if 'to' in wind_clean or 'from' in wind_clean or 'in' in wind_clean:
                                        wind_direction = wind_clean.split(' ', 1)[1].strip().upper()
                        except:
                            pass

                # Deep fetch live data to extract pitcher decisions cleanly
                try:
                    live_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/feed/live"
                    live_data = requests.get(live_url).json()
                    
                    if not officials_list:
                        officials_list = live_data.get('liveData', {}).get('boxscore', {}).get('officials', [])
                    
                    # Target liveData game records directly
                    live_decisions = live_data.get('gameData', {}).get('decisions', {})
                    win_id = live_decisions.get('winner', {}).get('id')
                    lose_id = live_decisions.get('loser', {}).get('id')
                    save_id = live_decisions.get('save', {}).get('id')
                except:
                    pass

                # Parse and seed game officials
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

                teams = g.get('teams', {})
                start_time = g.get('gameDate')
                start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ") if start_time else None

                conn.execute(text("""
                    INSERT INTO games (
                        game_pk, game_date, season, game_type, scheduled_start, park_id, home_team_id, away_team_id,
                        home_score, away_score, winning_pitcher_id, losing_pitcher_id, save_pitcher_id, day_night_type, is_doubleheader,
                        temperature_f, sky_condition, wind_speed_mph, wind_direction, home_plate_ump_id, first_base_ump_id, second_base_ump_id, third_base_ump_id
                    ) VALUES (
                        :game_pk, :game_date, :season, :game_type, :start, :park, :home, :away, :h_score, :a_score, :win, :lose, :save, :dn, :dh,
                        :temp, :sky, :w_spd, :w_dir, :hp, :fb, :sb, :tb
                    ) ON CONFLICT (game_pk) DO UPDATE SET
                        home_score = EXCLUDED.home_score, 
                        away_score = EXCLUDED.away_score,
                        winning_pitcher_id = EXCLUDED.winning_pitcher_id,
                        losing_pitcher_id = EXCLUDED.losing_pitcher_id,
                        save_pitcher_id = EXCLUDED.save_pitcher_id,
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
                    "home": teams.get('home', {}).get('team', {}).get('id'), "away": teams.get('away', {}).get('team', {}).get('id'),
                    "h_score": teams.get('home', {}).get('score'), "a_score": teams.get('away', {}).get('score'),
                    "win": win_id, "lose": lose_id, "save": save_id, "dn": g.get('dayNight'), "dh": dh_flag,
                    "temp": temp, "sky": sky, "w_spd": wind_spd, "w_dir": wind_direction, "hp": hp_id, "fb": fb_id, "sb": sb_id, "tb": tb_id
                })
    print(f"Core games mapping entries finalized for date window: {target_date}")
