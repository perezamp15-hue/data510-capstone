"""Central application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables."""

    app_env: Literal["development", "testing", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = Field(
        default="",
        description="SQLAlchemy-compatible PostgreSQL connection URL.",
    )

    mlb_api_base_url: str = "https://statsapi.mlb.com/api"
    request_timeout_seconds: int = 30
    request_max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def has_database_url(self) -> bool:
        """Return whether a database connection string was configured."""
        return bool(self.database_url.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached application settings object."""
    return Settings()
