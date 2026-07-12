from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analytics.config import get_settings
from analytics.database import (
    dispose_engine,
    test_database_connection,
)
from analytics.exceptions import AnalyticsError
from analytics.json_exporter import write_json
from analytics.repository import BaseballRepository

def configure_logging() -> None:
    """Configure console logging."""
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

def main() -> int:
    """Run all Phase One validation checks."""
    configure_logging()

    logger = logging.getLogger("phase_one")
    settings = get_settings()
    repository = BaseballRepository()

    logger.info("Starting MLB analytics Phase One validation.")

    try:
        database_information = test_database_connection()
        logger.info(
            "Connected to database: %s",
            database_information.get("database_name"),
        )

        table_counts = repository.get_table_counts()
        available_seasons = repository.get_available_seasons()
        latest_game_date = repository.get_latest_game_date()
        teams = repository.get_teams()
        parks = repository.get_parks()

        health_payload = {
            "status": "healthy",
            "generated_at_utc": datetime.now(timezone.utc),
            "database": {
                "database_name": database_information.get("database_name"),
                "database_user": database_information.get("database_user"),
                "server_time": database_information.get("server_time"),
            },
            "warehouse": {
                "latest_game_date": latest_game_date,
                "available_seasons": available_seasons,
                "table_counts": table_counts,
                "team_count": len(teams),
                "park_count": len(parks),
            },
        }

        output_path = write_json(
            settings.health_output_dir / "database_summary.json",
            health_payload,
        )

        print("\nDATABASE CONNECTION")
        print("-" * 60)
        print(f"Database: {database_information['database_name']}")
        print(f"User:     {database_information['database_user']}")
        print(f"Time:     {database_information['server_time']}")
        print("\nTABLE COUNTS")
        print("-" * 60)
        print(table_counts.to_string(index=False))
        print("\nWAREHOUSE INFORMATION")
        print("-" * 60)
        print(f"Available seasons: {available_seasons}")
        print(f"Latest game date:  {latest_game_date}")
        print(f"Teams:             {len(teams)}")
        print(f"Parks:             {len(parks)}")
        print("\nEXPORT")
        print("-" * 60)
        print(f"Created: {output_path}")
        print("\nPhase One validation completed successfully.")
        return 0

    except AnalyticsError as exc:
        logger.exception("Phase One validation failed: %s", exc)
        return 1

    except Exception:
        logger.exception("An unexpected Phase One error occurred.")
        return 1

    finally:
        dispose_engine()

if __name__ == "__main__":
    raise SystemExit(main())