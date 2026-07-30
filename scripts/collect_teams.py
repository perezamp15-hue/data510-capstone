"""Run the MLB team collector."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.collectors.teams import collect_teams


def configure_logging(verbose: bool = False) -> None:
    """Configure console logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(
        description="Collect MLB teams into PostgreSQL."
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )

    return parser.parse_args()


def main() -> int:
    """Run the team collection process."""
    arguments = parse_arguments()
    configure_logging(arguments.verbose)

    try:
        metrics = collect_teams()
    except Exception as exc:
        logging.exception("Team collection failed: %s", exc)
        return 1

    print()
    print("MLB team collection succeeded")
    print(f"Records read:     {metrics.records_read}")
    print(f"Records inserted: {metrics.records_inserted}")
    print(f"Records updated:  {metrics.records_updated}")
    print(f"Records rejected: {metrics.records_rejected}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())