"""Evaluate frequency baseline using a chronological holdout."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import PitchSequenceFeature


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; use YYYY-MM-DD."
        ) from exc


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the next-pitch frequency baseline."
    )

    parser.add_argument(
        "--train-end-date",
        type=parse_date,
        required=True,
    )

    parser.add_argument(
        "--test-start-date",
        type=parse_date,
        required=True,
    )

    parser.add_argument(
        "--test-end-date",
        type=parse_date,
        required=True,
    )

    parser.add_argument(
        "--minimum-group-size",
        type=int,
        default=10,
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    with session_scope() as session:
        training_rows = session.execute(
            select(
                PitchSequenceFeature.pitcher_id,
                PitchSequenceFeature.balls_before_pitch,
                PitchSequenceFeature.strikes_before_pitch,
                PitchSequenceFeature.batter_side,
                PitchSequenceFeature.previous_pitch_type,
                PitchSequenceFeature.target_pitch_type,
            )
            .where(
                PitchSequenceFeature.game_date
                <= arguments.train_end_date
            )
        ).all()

        test_rows = session.execute(
            select(
                PitchSequenceFeature.pitcher_id,
                PitchSequenceFeature.balls_before_pitch,
                PitchSequenceFeature.strikes_before_pitch,
                PitchSequenceFeature.batter_side,
                PitchSequenceFeature.previous_pitch_type,
                PitchSequenceFeature.target_pitch_type,
            )
            .where(
                PitchSequenceFeature.game_date.between(
                    arguments.test_start_date,
                    arguments.test_end_date,
                )
            )
        ).all()

    grouped_counts: dict[
        tuple[int, int, int, str | None, str | None],
        Counter[str],
    ] = defaultdict(Counter)

    pitcher_counts: dict[int, Counter[str]] = defaultdict(Counter)
    league_counts: Counter[str] = Counter()

    for row in training_rows:
        key = (
            row.pitcher_id,
            row.balls_before_pitch,
            row.strikes_before_pitch,
            row.batter_side,
            row.previous_pitch_type,
        )

        grouped_counts[key][row.target_pitch_type] += 1
        pitcher_counts[row.pitcher_id][row.target_pitch_type] += 1
        league_counts[row.target_pitch_type] += 1

    top_one_correct = 0
    top_three_correct = 0
    evaluated = 0

    for row in test_rows:
        key = (
            row.pitcher_id,
            row.balls_before_pitch,
            row.strikes_before_pitch,
            row.batter_side,
            row.previous_pitch_type,
        )

        counts = grouped_counts.get(key)

        if not counts or sum(counts.values()) < arguments.minimum_group_size:
            counts = pitcher_counts.get(row.pitcher_id)

        if not counts:
            counts = league_counts

        predictions = [
            pitch_type
            for pitch_type, _ in counts.most_common(3)
        ]

        if not predictions:
            continue

        evaluated += 1

        if row.target_pitch_type == predictions[0]:
            top_one_correct += 1

        if row.target_pitch_type in predictions:
            top_three_correct += 1

    if evaluated == 0:
        print("No test rows could be evaluated.")
        return 1

    print()
    print("FREQUENCY BASELINE EVALUATION")
    print("=" * 60)
    print(f"Training rows:  {len(training_rows)}")
    print(f"Test rows:      {len(test_rows)}")
    print(f"Evaluated rows: {evaluated}")
    print(f"Top-1 accuracy: {top_one_correct / evaluated:.2%}")
    print(f"Top-3 accuracy: {top_three_correct / evaluated:.2%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())