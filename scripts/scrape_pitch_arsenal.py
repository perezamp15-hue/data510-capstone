import pandas as pd
from db_client import get_engine

def run():
    print("Deriving Custom Pitch Arsenals via Statcast historical records...")
    query = """
    SELECT 
        pitcher_id,
        pitch_type,
        COUNT(*)::float / SUM(COUNT(*)) OVER(PARTITION BY pitcher_id) * 100 AS usage_pct,
        AVG(release_speed) AS avg_velocity,
        AVG(release_spin_rate) AS avg_spin,
        AVG(release_extension) AS avg_extension,
        AVG(release_pos_z) AS avg_release_height
    FROM statcast_pitches
    WHERE pitch_type IS NOT NULL
    GROUP BY pitcher_id, pitch_type;
    """
    engine = get_engine()
    df = pd.read_sql(query, engine)
    
    if not df.empty:
        df.to_sql('pitch_arsenals', engine, if_exists='replace', index=False)
        print("Pitch arsenals successfully recalculated.")

if __name__ == '__main__':
    run()
