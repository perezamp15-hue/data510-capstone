"""Backfill games and pitches in restartable windows."""

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


from baseball_capstone.collectors.games import collect_games
from baseball_capstone.collectors.pitches import collect_pitches


LOGGER = logging.getLogger(__name__)


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; use YYYY-MM-DD."
        ) from exc


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill MLB games and pitches."
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--end-date",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--game-window-days",
        type=int,
        default=28,
    )
    parser.add_argument(
        "--pitch-window-days",
        type=int,
        default=7,
    )
    parser.add_argument(
        "--pitch-limit",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--games-only",
        action="store_true",
    )
    parser.add_argument(
        "--pitches-only",
        action="store_true",
    )

    return parser.parse_args()


def date_windows(
    start_date: date,
    end_date: date,
    window_days: int,
):
    """Yield inclusive date windows."""
    current_start = start_date

    while current_start <= end_date:
        current_end = min(
            current_start + timedelta(days=window_days - 1),
            end_date,
        )

        yield current_start, current_end
        current_start = current_end + timedelta(days=1)


def main() -> int:
    arguments = parse_arguments()

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    if arguments.end_date < arguments.start_date:
        raise ValueError(
            "The end date cannot be before the start date."
        )

    if not arguments.pitches_only:
        for window_start, window_end in date_windows(
            arguments.start_date,
            arguments.end_date,
            arguments.game_window_days,
        ):
            LOGGER.info(
                "Backfilling games from %s through %s",
                window_start,
                window_end,
            )

            metrics = collect_games(
                start_date=window_start,
                end_date=window_end,
            )

            LOGGER.info(
                "Games: read=%s inserted=%s updated=%s rejected=%s",
                metrics.records_read,
                metrics.records_inserted,
                metrics.records_updated,
                metrics.records_rejected,
            )

    if not arguments.games_only:
        for window_start, window_end in date_windows(
            arguments.start_date,
            arguments.end_date,
            arguments.pitch_window_days,
        ):
            LOGGER.info(
                "Backfilling pitches from %s through %s",
                window_start,
                window_end,
            )

            metrics = collect_pitches(
                start_date=window_start,
                end_date=window_end,
                force=False,
                replace=False,
                limit=arguments.pitch_limit,
            )

            LOGGER.info(
                "Pitches: games=%s inserted=%s "
                "updated=%s failed=%s",
                metrics.records_read,
                metrics.records_inserted,
                metrics.records_updated,
                metrics.records_rejected,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())