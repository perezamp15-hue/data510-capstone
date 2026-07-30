"""Generate predictions from the saved next-pitch model."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


@dataclass(frozen=True, slots=True)
class ModelPitchProbability:
    """One model-generated pitch probability."""

    pitch_type: str
    probability: float


@dataclass(frozen=True, slots=True)
class NextPitchPrediction:
    """Ranked next-pitch model prediction."""

    probabilities: list[ModelPitchProbability]


def predict_next_pitch(
    *,
    model_path: Path,
    pitcher_id: int,
    batter_id: int,
    pitcher_hand: str | None,
    batter_side: str | None,
    balls: int,
    strikes: int,
    outs: int,
    inning: int,
    inning_half: str | None,
    previous_pitch_type: str | None = None,
    previous_pitch_zone: str | None = None,
    previous_pitch_result: str | None = None,
    second_previous_pitch_type: str | None = None,
    second_previous_pitch_zone: str | None = None,
    third_previous_pitch_type: str | None = None,
    runner_on_first: bool = False,
    runner_on_second: bool = False,
    runner_on_third: bool = False,
    top_n: int = 5,
) -> NextPitchPrediction:
    """Predict ranked next-pitch probabilities."""
    if not model_path.exists():
        raise FileNotFoundError(
            f"Model artifact does not exist: {model_path}"
        )

    artifact: dict[str, Any] = joblib.load(model_path)
    model = artifact["model"]

    row = pd.DataFrame(
        [
            {
                "pitcher_id": str(pitcher_id),
                "batter_id": str(batter_id),
                "pitcher_hand": pitcher_hand,
                "batter_side": batter_side,
                "previous_pitch_type": previous_pitch_type,
                "previous_pitch_zone": previous_pitch_zone,
                "previous_pitch_result": previous_pitch_result,
                "second_previous_pitch_type": (
                    second_previous_pitch_type
                ),
                "second_previous_pitch_zone": (
                    second_previous_pitch_zone
                ),
                "third_previous_pitch_type": (
                    third_previous_pitch_type
                ),
                "inning_half": inning_half,
                "balls_before_pitch": balls,
                "strikes_before_pitch": strikes,
                "outs_before_pitch": outs,
                "inning": inning,
                "runner_on_first": int(runner_on_first),
                "runner_on_second": int(runner_on_second),
                "runner_on_third": int(runner_on_third),
            }
        ]
    )

    probabilities = model.predict_proba(row)[0]
    classifier = model.named_steps["classifier"]
    classes = classifier.classes_

    ranked = sorted(
        zip(classes, probabilities, strict=True),
        key=lambda item: item[1],
        reverse=True,
    )

    results = [
        ModelPitchProbability(
            pitch_type=str(pitch_type),
            probability=float(probability),
        )
        for pitch_type, probability in ranked[:top_n]
    ]

    return NextPitchPrediction(probabilities=results)