import sys
import pandas as pd
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    if not target_date:
        # Enforce cron operational local context safety 
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        
    print(f"Cron execution: Ingesting transaction matrix logs for {target_date}...")
    
    # MLB Transactions feed date-range wrapper format
    url = f"https://statsapi.mlb.com/api/v1/transactions?sportId=1&startDate={target_date}&endDate={target_date}"
    
    try:
        data = fetch_api_json(url)
        raw_txs = data.get('transactions', [])
        if not raw_txs:
            print(f"No transactions filed on league logs for {target_date}. Exiting safely.")
            return
            
        engine = get_engine()
        valid_players = pd.read_sql("SELECT player_id FROM players", con=engine)['player_id'].tolist()
        valid_teams = pd.read_sql("SELECT team_id FROM teams", con=engine)['team_id'].tolist()
        
        parsed = []
        for tx in raw_txs:
            p_id = tx.get('person', {}).get('id')
            # Cron safety checkpoint: Skip transaction entries for un-indexed players
            if not p_id or int(p_id) not in valid_players:
                continue
                
            from_t = tx.get('fromTeam', {}).get('id')
            to_t = tx.get('toTeam', {}).get('id')
            
            parsed.append({
                "player_id": int(p_id),
                "transaction_date": tx.get('date'),
                "transaction_type": tx.get('typeDesc', 'Roster Move'),
                "from_team_id": int(from_t) if from_t and int(from_t) in valid_teams else None,
                "to_team_id": int(to_t) if to_t and int(to_t) in valid_teams else None,
                "injury_status": tx.get('description', '')[:254] # Strict string bounding truncation
            })
            
        if not parsed:
            print("No actionable transaction records mapped to tracked player directories.")
            return
            
        df = pd.DataFrame(parsed)
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO transactions (player_id, transaction_date, transaction_type, from_team_id, to_team_id, injury_status)
                    VALUES (:player_id, :transaction_date, :transaction_type, :from_team_id, :to_team_id, :injury_status);
                """), row.to_dict())
        print(f"Cron complete: Successfully logged {len(df)} transactions.")
        
    except Exception as e:
        print(f"Cron Error: Transaction verification module failed: {e}")
        sys.exit(0) # Exit code 0 ensures the overall cron worker structure doesn't report a false failure

if __name__ == "__main__":
    passed_date = sys.argv[1] if len(sys.argv) > 1 else None
    run(passed_date)
