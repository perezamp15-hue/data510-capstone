"""PostgreSQL engine and session helpers."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from baseball_capstone.config.settings import get_settings


def normalize_database_url(database_url: str) -> str:
    """Normalize a PostgreSQL URL for SQLAlchemy and psycopg 3."""
    database_url = database_url.strip()

    if database_url.startswith("postgres://"):
        return database_url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache the SQLAlchemy engine."""
    settings = get_settings()

    if not settings.has_database_url:
        raise RuntimeError(
            "DATABASE_URL is missing. Add it to the local .env file."
        )

    return create_engine(
        normalize_database_url(settings.database_url),
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 15},
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Create and cache the SQLAlchemy session factory."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional SQLAlchemy session."""
    session = get_session_factory()()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection() -> dict[str, str | int]:
    """Run a lightweight PostgreSQL connection test."""
    with get_engine().connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT
                    current_database() AS database_name,
                    current_user AS database_user,
                    version() AS postgres_version,
                    1 AS connection_test
                """
            )
        ).mappings().one()

    return dict(result)
