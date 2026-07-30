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


from baseball_capstone.collectors.pitches import (
    collect_pitches,
)


def parse_date(value: str) -> date:
    """Parse a date in YYYY-MM-DD format."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; use YYYY-MM-DD."
        ) from exc


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Collect MLB pitch-by-pitch data into PostgreSQL."
        )
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        help="Inclusive start date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
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
        "--workers",
        type=int,
        default=1,
        help=(
            "Number of games processed concurrently. "
            "Recommended: 2-4. Maximum: 8."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Reprocess games already marked as collected."
        ),
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "Delete and rebuild stored pitches for each "
            "selected game."
        ),
    )

    parser.add_argument(
        "--store-raw-payload",
        action="store_true",
        help=(
            "Store the raw JSON for every pitch. This increases "
            "database storage and slows large backfills."
        ),
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
    """Resolve the requested collection range."""
    if arguments.start_date or arguments.end_date:
        if (
            arguments.start_date is None
            or arguments.end_date is None
        ):
            raise ValueError(
                "--start-date and --end-date must be "
                "used together."
            )

        return (
            arguments.start_date,
            arguments.end_date,
        )

    if arguments.days_back < 0:
        raise ValueError(
            "--days-back cannot be negative."
        )

    end_date = date.today()
    start_date = end_date - timedelta(
        days=arguments.days_back
    )

    return start_date, end_date


def main() -> int:
    """Run pitch collection."""
    arguments = parse_arguments()

    logging.basicConfig(
        level=(
            logging.DEBUG
            if arguments.verbose
            else logging.INFO
        ),
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(threadName)s | %(name)s | %(message)s"
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
            workers=arguments.workers,
            store_raw_payload=(
                arguments.store_raw_payload
            ),
        )

    except Exception as exc:
        logging.exception(
            "Pitch collection failed: %s",
            exc,
        )
        return 1

    print()
    print("=" * 64)
    print("PITCH COLLECTION FINISHED")
    print("=" * 64)
    print(
        f"Date range:       "
        f"{start_date} through {end_date}"
    )
    print(f"Workers:          {arguments.workers}")
    print(f"Games selected:   {metrics.records_read}")
    print(f"Pitches inserted: {metrics.records_inserted}")
    print(f"Pitches updated:  {metrics.records_updated}")
    print(f"Games failed:     {metrics.records_rejected}")
    print(
        "Raw payloads:     "
        f"{'stored' if arguments.store_raw_payload else 'disabled'}"
    )

    return (
        1
        if metrics.records_rejected > 0
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
