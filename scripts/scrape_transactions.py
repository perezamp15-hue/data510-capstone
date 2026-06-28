import sys
import requests
from datetime import datetime
from sqlalchemy import text
from db_client import get_engine

def run(target_date):
    print(f"Loading Transaction Roster Actions for: {target_date}")
    engine = get_engine()
    
    url = f"https://statsapi.mlb.com/api/v1/transactions?sportId=1&date={target_date}"
    res = requests.get(url)
    if res.status_code != 200:
        return
    
    transactions = res.json().get('transactions', [])
    
    with engine.begin() as conn:
        for t in transactions:
            player_id = t.get('person', {}).get('id')
            if not player_id:
                continue
                
            # Verify the player exists in our lookup dimension table to respect FK rules
            player_check = conn.execute(text("SELECT player_id FROM players WHERE player_id = :id"), {"id": player_id}).fetchone()
            if not player_check:
                # Fast baseline seed to protect constraints pathing continuity
                conn.execute(text("INSERT INTO players (player_id, full_name, is_active) VALUES (:id, :name, true) ON CONFLICT DO NOTHING;"), {"id": player_id, "name": t.get('person', {}).get('fullName', 'Unknown')})

            conn.execute(text("""
                INSERT INTO transactions (player_id, transaction_date, transaction_type, from_team_id, to_team_id, injury_status)
                VALUES (:player_id, :date, :type, :from_team, :to_team, :injury);
            """), {
                "player_id": player_id, "date": datetime.strptime(target_date, "%Y-%m-%d").date(),
                "type": t.get('typeCode'), "from_team": t.get('fromTeam', {}).get('id'),
                "to_team": t.get('toTeam', {}).get('id'), "injury": t.get('description')
            })
    print(f"Logged {len(transactions)} transaction actions.")
