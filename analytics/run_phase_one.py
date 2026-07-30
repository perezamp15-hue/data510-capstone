from __future__ import annotations

import logging

from analytics.database import read_dataframe, test_database_connection

logger = logging.getLogger(__name__)

REQUIRED_TABLES = {
    "games", "parks", "players", "starting_lineups",
    "statcast_pitches", "teams", "transactions", "umpires",
}


def run_phase_one() -> None:
    """Perform lightweight warehouse validation; do not train models here."""
    test_database_connection()
    frame = read_dataframe(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        """
    )
    found = set(frame["table_name"].astype(str))
    missing = sorted(REQUIRED_TABLES - found)
    if missing:
        raise RuntimeError("Missing required tables: " + ", ".join(missing))
    logger.info("Phase-one validation passed for %d required tables", len(REQUIRED_TABLES))


if __name__ == "__main__":
    run_phase_one()
