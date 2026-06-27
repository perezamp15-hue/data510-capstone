import os
import sys
import requests
from sqlalchemy import create_engine

def get_engine():
    # Looks for Railway variables first, falls back to a default local target
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("CRITICAL: DATABASE_URL environment variable is missing!")
        sys.exit(1)
    # Patch for modern SQLAlchemy versions which require postgresql:// instead of postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    return create_engine(database_url)

def fetch_api_json(url):
    """Safely retrieves payloads from the MLB API with automated error handling."""
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()
