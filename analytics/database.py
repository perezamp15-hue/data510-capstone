from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Mapping

import pandas as pd
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from analytics.config import get_settings
from analytics.exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create one reusable, conservative PostgreSQL connection pool."""
    settings = get_settings()
    statement_timeout = int(__import__("os").getenv("DB_STATEMENT_TIMEOUT_MS", "300000"))

    try:
        return create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=30,
            pool_recycle=settings.db_pool_recycle_seconds,
            connect_args={
                "connect_timeout": settings.db_connect_timeout_seconds,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
                "options": f"-c statement_timeout={statement_timeout}",
            },
        )
    except (SQLAlchemyError, ValueError) as exc:
        raise DatabaseConnectionError(
            "SQLAlchemy could not create the PostgreSQL engine."
        ) from exc


def test_database_connection() -> dict[str, Any]:
    """Test PostgreSQL and return non-secret connection metadata."""
    try:
        with get_engine().connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT current_database() AS database_name,
                           current_user AS database_user,
                           version() AS postgres_version,
                           NOW() AS server_time
                    """
                )
            ).mappings().one()
        return dict(row)
    except SQLAlchemyError as exc:
        logger.exception("Database connection test failed.")
        raise DatabaseConnectionError(
            "Unable to connect to PostgreSQL. Check DATABASE_URL and networking."
        ) from exc


def read_dataframe(query: str, parameters: Mapping[str, Any] | None = None) -> pd.DataFrame:
    try:
        with get_engine().connect() as connection:
            return pd.read_sql_query(text(query), connection, params=dict(parameters or {}))
    except SQLAlchemyError as exc:
        logger.exception("Database query failed.")
        raise DatabaseConnectionError("A PostgreSQL query failed.") from exc


def read_scalar(query: str, parameters: Mapping[str, Any] | None = None) -> Any:
    try:
        with get_engine().connect() as connection:
            return connection.execute(text(query), dict(parameters or {})).scalar_one_or_none()
    except SQLAlchemyError as exc:
        logger.exception("Scalar database query failed.")
        raise DatabaseConnectionError("A PostgreSQL scalar query failed.") from exc


def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
        get_engine.cache_clear()
