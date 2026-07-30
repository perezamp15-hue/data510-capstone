"""Run the frequency-based next-pitch predictor."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.analytics.pitch_baseline import (
    predict_next_pitch_frequency,
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
    """Parse prediction arguments."""
    parser = argparse.ArgumentParser(
        description="Predict the next pitch using historical frequencies."
    )

    parser.add_argument(
        "--pitcher-id",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--batter-id",
        type=int,
    )

    parser.add_argument(
        "--balls",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--strikes",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--batter-side",
        choices=["L", "R", "S"],
    )

    parser.add_argument(
        "--previous-pitch-type",
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
        "--minimum-sample",
        type=int,
        default=20,
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
    )

    return parser.parse_args()


def main() -> int:
    """Generate and print a baseline prediction."""
    arguments = parse_arguments()

    try:
        prediction = predict_next_pitch_frequency(
            pitcher_id=arguments.pitcher_id,
            batter_id=arguments.batter_id,
            balls=arguments.balls,
            strikes=arguments.strikes,
            batter_side=arguments.batter_side,
            previous_pitch_type=arguments.previous_pitch_type,
            start_date=arguments.start_date,
            end_date=arguments.end_date,
            minimum_sample=arguments.minimum_sample,
            top_n=arguments.top_n,
        )
    except Exception as exc:
        print(f"Prediction failed: {exc}")
        return 1

    print()
    print("NEXT-PITCH FREQUENCY BASELINE")
    print("=" * 60)
    print(f"Pitcher ID:       {prediction.pitcher_id}")
    print(f"Batter ID:        {prediction.batter_id or 'not supplied'}")
    print(
        f"Count:            "
        f"{prediction.balls}-{prediction.strikes}"
    )
    print(
        f"Batter side:      "
        f"{prediction.batter_side or 'unknown'}"
    )
    print(
        f"Previous pitch:   "
        f"{prediction.previous_pitch_type or 'none'}"
    )
    print(f"Fallback level:   {prediction.fallback_level}")
    print(f"Historical sample:{prediction.sample_size:>8}")
    print()

    if not prediction.probabilities:
        print("No historical prediction was available.")
        return 1

    print("Pitch probabilities:")

    for rank, probability in enumerate(
        prediction.probabilities,
        start=1,
    ):
        print(
            f"{rank}. {probability.pitch_type:<6} "
            f"{probability.probability:>7.1%} "
            f"({probability.pitch_count} pitches)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())