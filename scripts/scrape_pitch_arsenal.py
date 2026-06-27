import sys
import pandas as pd
from db_client import get_engine
from sqlalchemy import text

def run():
    print("Recalculating custom pitch arsenals...")
    engine = get_engine()
    sql = "SELECT pitcher_id, pitch_type, release_velocity FROM statcast_pitches WHERE pitch_type IS NOT NULL AND release_velocity IS NOT NULL"
    try:
        df = pd.read_sql(sql, con=engine)
        if df.empty: return
        total_counts = df.groupby('pitcher_id')['pitch_type'].count().reset_index(name='total')
        grouped = df.groupby(['pitcher_id', 'pitch_type']).agg(average_velocity=('release_velocity', 'mean'), count_type=('release_velocity', 'count')).reset_index()
        merged = pd.merge(grouped, total_counts, on='pitcher_id')
        merged['selection_usage_rate'] = (merged['count_type'] / merged['total']) * 100
        with engine.begin() as conn:
            for _, row in merged.iterrows():
                conn.execute(text("""
                    INSERT INTO pitch_arsenals (pitcher_id, pitch_type, average_velocity, selection_usage_rate)
                    VALUES (:pitcher_id, :pitch_type, :average_velocity, :selection_usage_rate)
                    ON CONFLICT (pitcher_id, pitch_type) DO UPDATE SET average_velocity = EXCLUDED.average_velocity, selection_usage_rate = EXCLUDED.selection_usage_rate;
                """), {"pitcher_id": int(row['pitcher_id']), "pitch_type": row['pitch_type'], "average_velocity": float(row['average_velocity']), "selection_usage_rate": float(row['selection_usage_rate'])})
    except Exception as e: print(f"Arsenal Error: {e}")

if __name__ == "__main__": run()
