"""Verify that the application can connect to PostgreSQL."""

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import check_database_connection


def main() -> int:
    """Test the configured PostgreSQL connection."""
    try:
        database_information = check_database_connection()
    except Exception as exc:
        print(f"Database connection failed: {exc}")
        return 1

    print("Database connection succeeded.")
    print(json.dumps(database_information, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
