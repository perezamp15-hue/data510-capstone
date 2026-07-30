"""Predict the next pitch with the trained model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.models.predict_next_pitch import (
    predict_next_pitch,
)


def parse_arguments() -> argparse.Namespace:
    """Parse prediction context."""
    parser = argparse.ArgumentParser(
        description="Predict the next pitch with the ML model."
    )

    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            "models/artifacts/next_pitch_model.joblib"
        ),
    )

    parser.add_argument("--pitcher-id", type=int, required=True)
    parser.add_argument("--batter-id", type=int, required=True)
    parser.add_argument("--pitcher-hand", choices=["L", "R"])
    parser.add_argument("--batter-side", choices=["L", "R", "S"])
    parser.add_argument("--balls", type=int, required=True)
    parser.add_argument("--strikes", type=int, required=True)
    parser.add_argument("--outs", type=int, default=0)
    parser.add_argument("--inning", type=int, default=1)
    parser.add_argument("--inning-half")
    parser.add_argument("--previous-pitch-type")
    parser.add_argument("--previous-pitch-zone")
    parser.add_argument("--previous-pitch-result")
    parser.add_argument("--second-previous-pitch-type")
    parser.add_argument("--second-previous-pitch-zone")
    parser.add_argument("--third-previous-pitch-type")
    parser.add_argument("--runner-on-first", action="store_true")
    parser.add_argument("--runner-on-second", action="store_true")
    parser.add_argument("--runner-on-third", action="store_true")
    parser.add_argument("--top-n", type=int, default=5)

    return parser.parse_args()


def main() -> int:
    """Generate one model prediction."""
    arguments = parse_arguments()

    try:
        prediction = predict_next_pitch(
            model_path=arguments.model,
            pitcher_id=arguments.pitcher_id,
            batter_id=arguments.batter_id,
            pitcher_hand=arguments.pitcher_hand,
            batter_side=arguments.batter_side,
            balls=arguments.balls,
            strikes=arguments.strikes,
            outs=arguments.outs,
            inning=arguments.inning,
            inning_half=arguments.inning_half,
            previous_pitch_type=arguments.previous_pitch_type,
            previous_pitch_zone=arguments.previous_pitch_zone,
            previous_pitch_result=arguments.previous_pitch_result,
            second_previous_pitch_type=(
                arguments.second_previous_pitch_type
            ),
            second_previous_pitch_zone=(
                arguments.second_previous_pitch_zone
            ),
            third_previous_pitch_type=(
                arguments.third_previous_pitch_type
            ),
            runner_on_first=arguments.runner_on_first,
            runner_on_second=arguments.runner_on_second,
            runner_on_third=arguments.runner_on_third,
            top_n=arguments.top_n,
        )
    except Exception as exc:
        print(f"Prediction failed: {exc}")
        return 1

    print()
    print("NEXT-PITCH MACHINE-LEARNING PREDICTION")
    print("=" * 64)

    for rank, result in enumerate(
        prediction.probabilities,
        start=1,
    ):
        print(
            f"{rank}. {result.pitch_type:<12} "
            f"{result.probability:>7.1%}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())