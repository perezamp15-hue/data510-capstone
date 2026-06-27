import requests
from sqlalchemy import create_engine
# Import the config instance from your root directory
from config import config

# Create the engine dynamically using the configuration mapping
engine = create_engine(config.DATABASE_URL)

def get_engine():
    return engine

def fetch_api_json(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
