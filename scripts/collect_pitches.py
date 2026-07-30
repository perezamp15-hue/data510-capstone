"""Run restartable MLB pitch-by-pitch collection."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.collectors.pitches import collect_pitches


def iso_date(value: str) -> date:
    """Parse a YYYY-MM-DD command-line date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; use YYYY-MM-DD."
        ) from exc


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Collect MLB pitch-by-pitch data into PostgreSQL."
    )

    parser.add_argument(
        "--start-date",
        type=iso_date,
        help="Inclusive start date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--end-date",
        type=iso_date,
        help="Inclusive end date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help=(
            "When dates are omitted, collect this many days "
            "before today through today. Default: 1."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of games to process.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess games already marked as collected.",
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete and rebuild pitches for each selected game.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )

    return parser.parse_args()


def resolve_dates(
    arguments: argparse.Namespace,
) -> tuple[date, date]:
    """Resolve the requested collection dates."""
    if arguments.start_date or arguments.end_date:
        if not arguments.start_date or not arguments.end_date:
            raise ValueError(
                "--start-date and --end-date must be used together."
            )

        return arguments.start_date, arguments.end_date

    if arguments.days_back < 0:
        raise ValueError("--days-back cannot be negative.")

    end_date = date.today()
    start_date = end_date - timedelta(days=arguments.days_back)

    return start_date, end_date


def main() -> int:
    """Run pitch collection."""
    arguments = parse_arguments()

    logging.basicConfig(
        level=logging.DEBUG if arguments.verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    try:
        start_date, end_date = resolve_dates(arguments)

        metrics = collect_pitches(
            start_date=start_date,
            end_date=end_date,
            force=arguments.force,
            replace=arguments.replace,
            limit=arguments.limit,
        )

    except Exception as exc:
        logging.exception("Pitch collection failed: %s", exc)
        return 1

    print()
    print("Pitch collection finished")
    print(f"Date range:       {start_date} through {end_date}")
    print(f"Games selected:   {metrics.records_read}")
    print(f"Pitches inserted: {metrics.records_inserted}")
    print(f"Pitches updated:  {metrics.records_updated}")
    print(f"Games failed:     {metrics.records_rejected}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
