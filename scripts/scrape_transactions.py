import sys
import pandas as pd
import numpy as np  # Imported to completely wipe out float NaNs
from datetime import datetime, timedelta
import pytz
from db_client import get_engine, fetch_api_json
from sqlalchemy import text

def run(target_date=None):
    if not target_date:
        local_tz = pytz.timezone('America/Los_Angeles')
        target_date = (datetime.now(local_tz) - timedelta(days=1)).strftime('%Y-%m-%d')
        
    url = f"https://statsapi.mlb.com/api/v1/transactions?sportId=1&startDate={target_date}&endDate={target_date}"
    try:
        data = fetch_api_json(url)
        raw_txs = data.get('transactions', [])
        if not raw_txs: 
            return
            
        engine = get_engine()
        valid_players = pd.read_sql("SELECT player_id FROM players", con=engine)['player_id'].tolist()
        valid_teams = pd.read_sql("SELECT team_id FROM teams", con=engine)['team_id'].tolist()
        
        parsed = []
        for tx in raw_txs:
            p_id = tx.get('person', {}).get('id')
            if not p_id or int(p_id) not in valid_players: 
                continue
                
            from_t = tx.get('fromTeam', {}).get('id')
            to_t = tx.get('toTeam', {}).get('id')
            
            # Cast strictly to python ints or None (eliminates decimal floats like 141.0)
            clean_from_team = int(from_t) if from_t and int(from_t) in valid_teams else None
            clean_to_team = int(to_t) if to_t and int(to_t) in valid_teams else None
            
            parsed.append({
                "player_id": int(p_id), 
                "transaction_date": tx.get('date'), 
                "transaction_type": tx.get('typeDesc', 'Roster Move'),
                "from_team_id": clean_from_team,
                "to_team_id": clean_to_team, 
                "injury_status": tx.get('description', '')[:254]
            })
            
        if not parsed: 
            return
            
        df = pd.DataFrame(parsed)
        
        # CRON SAFETY FIX: Strip out all pandas float NaN traces completely
        df = df.replace({np.nan: None})
        
        with engine.begin() as conn:
            for _, row in df.iterrows():
                conn.execute(text("""
                    INSERT INTO transactions (player_id, transaction_date, transaction_type, from_team_id, to_team_id, injury_status)
                    VALUES (:player_id, :transaction_date, :transaction_type, :from_team_id, :to_team_id, :injury_status);
                """), row.to_dict())
                
        print(f"Transactions updated successfully for {len(df)} movements.")
    except Exception as e: 
        print(f"Transactions Error: {e}")

if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
