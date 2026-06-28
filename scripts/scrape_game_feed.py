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

                # Fetch detailed boxscore endpoint data inline to handle contextual details
                box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                box_res = requests.get(box_url)
                temp, sky, wind_spd, wind_dir = None, None, None, None
                hp_id, fb_id, sb_id, tb_id = None, None, None, None
                
                if box_res.status_code == 200:
                    box_data = box_res.json()
                    # Parse weather details
                    info = box_data.get('info', [])
                    weather_str = next((i['value'] for i in info if i['label'] == 'Weather'), '')
                    if weather_str and ':' in weather_str:
                        try:
                            # Sample parse: "72 degrees, Sky Clear. Wind 5 mph out to CF"
                            parts = weather_str.split(',')
                            temp = int(parts[0].lower().replace('degrees', '').strip())
                            if len(parts) > 1:
                                sky = parts[1].strip()
                        except:
                            pass

                    # Parse field official positions
                    for off in box_data.get('officials', []):
                        oid = off['official']['id']
                        role = off['officialType']
                        
                        # Add tracking insert to lookup dimension safety step
                        conn.execute(text("INSERT INTO umpires (umpire_id, umpire_name) VALUES (:id, :name) ON CONFLICT DO NOTHING;"), {"id": oid, "name": off['official']['fullName']})
                        
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
                        home_score = EXCLUDED.home_score, away_score = EXCLUDED.away_score,
                        temperature_f = EXCLUDED.temperature_f, sky_condition = EXCLUDED.sky_condition;
                """), {
                    "game_pk": game_pk, "game_date": datetime.strptime(target_date, "%Y-%m-%d").date(), "season": g.get('season', 2023),
                    "game_type": g.get('gameType', 'R'), "start": start_dt, "park": g.get('venue', {}).get('id'),
                    "home": teams.get('home', {}).get('team', {}).get('id'), "away": teams.get('away', {}).get('team', {}).get('id'),
                    "h_score": teams.get('home', {}).get('score'), "a_score": teams.get('away', {}).get('score'),
                    "win": g.get('decisions', {}).get('winner', {}).get('id'), "lose": g.get('decisions', {}).get('loser', {}).get('id'),
                    "save": g.get('decisions', {}).get('save', {}).get('id'), "dn": g.get('dayNight'), "dh": g.get('doubleHeader') == 'Y',
                    "temp": temp, "sky": sky, "w_spd": wind_spd, "w_dir": wind_dir, "hp": hp_id, "fb": fb_id, "sb": sb_id, "tb": tb_id
                })
    print(f"Core games mapping entries finalized for date window: {target_date}")
