"""Build pitch-sequence model features."""

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


from baseball_capstone.features.pitch_sequences import (
    build_pitch_sequence_features,
)


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; use YYYY-MM-DD."
        ) from exc


def parse_arguments() -> argparse.Namespace:
    """Parse feature-build arguments."""
    parser = argparse.ArgumentParser(
        description="Build pitch sequence training features."
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help=(
            "When explicit dates are omitted, rebuild this many "
            "days before today through today. Default: 7."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
    )

    return parser.parse_args()


def resolve_dates(
    arguments: argparse.Namespace,
) -> tuple[date, date]:
    """Resolve the feature-build range."""
    if arguments.start_date or arguments.end_date:
        if not arguments.start_date or not arguments.end_date:
            raise ValueError(
                "--start-date and --end-date must be used together."
            )

        return arguments.start_date, arguments.end_date

    if arguments.days_back < 0:
        raise ValueError("--days-back cannot be negative.")

    end_date = date.today()
    start_date = end_date - timedelta(
        days=arguments.days_back
    )

    return start_date, end_date


def main() -> int:
    """Build sequence features."""
    arguments = parse_arguments()

    logging.basicConfig(
        level=(
            logging.DEBUG
            if arguments.verbose
            else logging.INFO
        ),
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    try:
        start_date, end_date = resolve_dates(arguments)

        result = build_pitch_sequence_features(
            start_date=start_date,
            end_date=end_date,
        )

    except Exception as exc:
        logging.exception(
            "Pitch sequence feature build failed: %s",
            exc,
        )
        return 1

    print()
    print("Pitch sequence feature build succeeded")
    print(f"Date range:     {result.start_date} to {result.end_date}")
    print(f"Rows deleted:   {result.rows_deleted}")
    print(f"Rows available: {result.rows_inserted}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())