from __future__ import annotations
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv
from analytics.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

def _read_positive_integer(name: str, default: int) -> int:
    """Read and validate a positive integer environment variable."""
    raw_value = os.getenv(name, str(default))

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be an integer. Received: {raw_value!r}"
        ) from exc

    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero.")

    return value

def _normalize_database_url(database_url: str) -> str:
    cleaned = database_url.strip()

    if cleaned.startswith("postgres://"):
        cleaned = cleaned.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )
    elif cleaned.startswith("postgresql://"):
        cleaned = cleaned.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    if not cleaned.startswith("postgresql+psycopg://"):
        raise ConfigurationError(
            "DATABASE_URL must be a PostgreSQL connection URL."
        )

    return cleaned


def _add_sslmode(database_url: str) -> str:
    """
    Set DB_SSLMODE=require for Railway's public connection when needed.
    Leave DB_SSLMODE unset if the URL already contains the correct option.
    """
    sslmode = os.getenv("DB_SSLMODE", "").strip()
    if not sslmode:
        return database_url

    parsed = urlsplit(database_url)
    query_values = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_values.setdefault("sslmode", sslmode)

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_values),
            parsed.fragment,
        )
    )


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""
    database_url: str
    project_root: Path
    output_dir: Path
    default_season: int
    db_pool_size: int
    db_max_overflow: int
    db_pool_recycle_seconds: int
    db_connect_timeout_seconds: int
    log_level: str

    @property
    def health_output_dir(self) -> Path:
        return self.output_dir / "health"

    @property
    def pitcher_output_dir(self) -> Path:
        return self.output_dir / "pitchers"

    @property
    def batter_output_dir(self) -> Path:
        return self.output_dir / "batters"

    @property
    def game_output_dir(self) -> Path:
        return self.output_dir / "games"

    @property
    def park_output_dir(self) -> Path:
        return self.output_dir / "parks"

    @property
    def matchup_output_dir(self) -> Path:
        return self.output_dir / "matchups"

    def create_output_directories(self) -> None:
        """Create all analytics output directories."""
        directories = (
            self.output_dir,
            self.health_output_dir,
            self.pitcher_output_dir,
            self.batter_output_dir,
            self.game_output_dir,
            self.park_output_dir,
            self.matchup_output_dir,
        )

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings."""
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise ConfigurationError(
            "DATABASE_URL is missing. Add it to your local .env file "
            "or configure it as an environment variable."
        )

    database_url = _normalize_database_url(database_url)
    database_url = _add_sslmode(database_url)

    output_value = os.getenv("ANALYTICS_OUTPUT_DIR", "exports")
    output_path = Path(output_value)

    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    default_season = _read_positive_integer(
        "ANALYTICS_DEFAULT_SEASON",
        2026,
    )

    settings = Settings(
        database_url=database_url,
        project_root=PROJECT_ROOT,
        output_dir=output_path,
        default_season=default_season,
        db_pool_size=_read_positive_integer("DB_POOL_SIZE", 5),
        db_max_overflow=_read_positive_integer("DB_MAX_OVERFLOW", 5),
        db_pool_recycle_seconds=_read_positive_integer(
            "DB_POOL_RECYCLE_SECONDS",
            300,
        ),
        db_connect_timeout_seconds=_read_positive_integer(
            "DB_CONNECT_TIMEOUT_SECONDS",
            15,
        ),
        log_level=os.getenv("ANALYTICS_LOG_LEVEL", "INFO").upper(),
    )

    settings.create_output_directories()
    return settings