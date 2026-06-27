import os
import sys
import requests
from sqlalchemy import create_engine

def get_engine():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("CRITICAL: DATABASE_URL environment variable is missing!")
        sys.exit(1)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return create_engine(database_url)

def fetch_api_json(url):
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()
