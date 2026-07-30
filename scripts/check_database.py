from __future__ import annotations

import json
import sys

from analytics.database import dispose_engine, test_database_connection


def main() -> int:
    try:
        result = test_database_connection()
        safe = {
            "database_name": result["database_name"],
            "database_user": result["database_user"],
            "server_time": str(result["server_time"]),
            "postgres_version": str(result["postgres_version"]).split(",")[0],
        }
        print(json.dumps(safe, indent=2))
        return 0
    except Exception as exc:
        print(f"Database check failed: {exc}", file=sys.stderr)
        return 1
    finally:
        dispose_engine()


if __name__ == "__main__":
    raise SystemExit(main())
