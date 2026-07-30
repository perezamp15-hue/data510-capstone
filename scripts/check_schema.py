"""Display the tables currently available in PostgreSQL."""

import sys
from pathlib import Path

from sqlalchemy import inspect


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import get_engine


EXPECTED_TABLES = {
    "alembic_version",
    "collection_runs",
    "games",
    "parks",
    "pitches",
    "players",
    "teams",
}


def main() -> int:
    inspector = inspect(get_engine())
    existing_tables = set(inspector.get_table_names())

    print("Database tables:")

    for table_name in sorted(existing_tables):
        print(f"  - {table_name}")

    missing_tables = EXPECTED_TABLES - existing_tables

    if missing_tables:
        print("\nMissing expected tables:")

        for table_name in sorted(missing_tables):
            print(f"  - {table_name}")

        return 1

    print("\nSchema verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())