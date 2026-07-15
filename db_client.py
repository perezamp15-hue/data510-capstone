import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


load_dotenv()


def get_engine() -> Engine:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing. "
            "Add it to the project .env file."
        )

    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return create_engine(
        database_url,
        pool_pre_ping=True,
    )

def fetch_api_json(url):
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()
