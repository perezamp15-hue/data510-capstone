"""Train the machine-learning next-pitch classifier."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.models.next_pitch_model import (
    train_next_pitch_model,
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
    """Parse model-training options."""
    parser = argparse.ArgumentParser(
        description="Train the next-pitch classifier."
    )

    parser.add_argument(
        "--training-start-date",
        type=parse_date,
        required=True,
    )

    parser.add_argument(
        "--training-end-date",
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
        "--output",
        type=Path,
        default=Path(
            "models/artifacts/next_pitch_model.joblib"
        ),
    )

    return parser.parse_args()


def main() -> int:
    """Train and report model performance."""
    arguments = parse_arguments()

    try:
        result = train_next_pitch_model(
            training_start_date=(
                arguments.training_start_date
            ),
            training_end_date=(
                arguments.training_end_date
            ),
            test_start_date=arguments.test_start_date,
            test_end_date=arguments.test_end_date,
            output_path=arguments.output,
        )
    except Exception as exc:
        print(f"Model training failed: {exc}")
        return 1

    metrics = result.evaluation

    print()
    print("NEXT-PITCH MODEL TRAINING")
    print("=" * 64)
    print(f"Training rows:      {metrics.training_rows}")
    print(f"Test rows:          {metrics.test_rows}")
    print(f"Top-1 accuracy:     {metrics.top_one_accuracy:.2%}")
    print(f"Top-3 accuracy:     {metrics.top_three_accuracy:.2%}")
    print(f"Macro F1:           {metrics.macro_f1:.4f}")
    print(
        "Multiclass log loss: "
        f"{metrics.multiclass_log_loss:.4f}"
    )
    print(f"Classes:            {', '.join(result.classes)}")
    print(f"Model saved to:     {result.output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())