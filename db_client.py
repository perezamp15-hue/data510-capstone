from __future__ import annotations

import os
from functools import lru_cache

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is missing. "
            "Add it to the project .env file or Railway variables."
        )
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create one shared, bounded SQLAlchemy engine per process."""
    return create_engine(
        _database_url(),
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "2")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "1")),
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "300")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30")),
        connect_args={"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "15"))},
    )


def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()


def fetch_api_json(url: str):
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    return response.json()
