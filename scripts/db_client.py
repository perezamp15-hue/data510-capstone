import os
import requests
import pandas as pd
from sqlalchemy import create_engine

# Pull connection string directly from Railway Environment
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/gmsim")

# Fix protocol prefix for SQLAlchemy if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def get_engine():
    return engine

def fetch_api_json(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
