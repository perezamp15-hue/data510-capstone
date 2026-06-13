"""
Data Science Studio Scrum (DS3) - Railway Database Sync Module
Description: Automatically streams processed metrics into Railway PostgreSQL.
"""
import os
import sys
import pandas as pd
from sqlalchemy import create_engine

def upload_processed_data_to_railway():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL missing. Skipping database streaming phase.")
        return
        
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    cleaned_data_path = "data/processed/cleaned_at_bats.csv"
    if not os.path.exists(cleaned_data_path):
        sys.exit(1)
        
    df = pd.read_csv(cleaned_data_path)
    engine = create_engine(database_url)
    df.to_sql("cleaned_at_bats", con=engine, if_exists="replace", index=False)
    print("Database sync complete. Cleaned tables are live in your cloud instance!")

if __name__ == "__main__":
    upload_processed_data_to_railway()
