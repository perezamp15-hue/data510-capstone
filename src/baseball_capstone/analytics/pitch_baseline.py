"""Frequency-based next-pitch predictor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text

from baseball_capstone.database.engine import session_scope


@dataclass(frozen=True, slots=True)
class PitchProbability:
    """Probability assigned to one candidate pitch type."""

    pitch_type: str
    pitch_count: int
    probability: float


@dataclass(frozen=True, slots=True)
class BaselinePrediction:
    """Frequency baseline prediction result."""

    pitcher_id: int
    batter_id: int | None
    balls: int
    strikes: int
    batter_side: str | None
    previous_pitch_type: str | None
    sample_size: int
    fallback_level: str
    probabilities: list[PitchProbability]


QUERY_LEVEL_ONE = text(
    """
    SELECT
        target_pitch_type,
        COUNT(*) AS pitch_count
    FROM pitch_sequence_features
    WHERE pitcher_id = :pitcher_id
      AND balls_before_pitch = :balls
      AND strikes_before_pitch = :strikes
      AND (:batter_side IS NULL OR batter_side = :batter_side)
      AND (
            (:previous_pitch_type IS NULL AND previous_pitch_type IS NULL)
            OR previous_pitch_type = :previous_pitch_type
          )
      AND game_date BETWEEN :start_date AND :end_date
    GROUP BY target_pitch_type
    ORDER BY pitch_count DESC, target_pitch_type
    """
)


QUERY_LEVEL_TWO = text(
    """
    SELECT
        target_pitch_type,
        COUNT(*) AS pitch_count
    FROM pitch_sequence_features
    WHERE pitcher_id = :pitcher_id
      AND balls_before_pitch = :balls
      AND strikes_before_pitch = :strikes
      AND (:batter_side IS NULL OR batter_side = :batter_side)
      AND game_date BETWEEN :start_date AND :end_date
    GROUP BY target_pitch_type
    ORDER BY pitch_count DESC, target_pitch_type
    """
)


QUERY_LEVEL_THREE = text(
    """
    SELECT
        target_pitch_type,
        COUNT(*) AS pitch_count
    FROM pitch_sequence_features
    WHERE pitcher_id = :pitcher_id
      AND balls_before_pitch = :balls
      AND strikes_before_pitch = :strikes
      AND game_date BETWEEN :start_date AND :end_date
    GROUP BY target_pitch_type
    ORDER BY pitch_count DESC, target_pitch_type
    """
)


QUERY_LEVEL_FOUR = text(
    """
    SELECT
        target_pitch_type,
        COUNT(*) AS pitch_count
    FROM pitch_sequence_features
    WHERE pitcher_id = :pitcher_id
      AND game_date BETWEEN :start_date AND :end_date
    GROUP BY target_pitch_type
    ORDER BY pitch_count DESC, target_pitch_type
    """
)


QUERY_LEAGUE_FALLBACK = text(
    """
    SELECT
        target_pitch_type,
        COUNT(*) AS pitch_count
    FROM pitch_sequence_features
    WHERE balls_before_pitch = :balls
      AND strikes_before_pitch = :strikes
      AND (:batter_side IS NULL OR batter_side = :batter_side)
      AND game_date BETWEEN :start_date AND :end_date
    GROUP BY target_pitch_type
    ORDER BY pitch_count DESC, target_pitch_type
    """
)


def rows_to_probabilities(
    rows: list[Any],
) -> tuple[int, list[PitchProbability]]:
    """Convert grouped counts into normalized probabilities."""
    total = sum(int(row.pitch_count) for row in rows)

    if total == 0:
        return 0, []

    probabilities = [
        PitchProbability(
            pitch_type=str(row.target_pitch_type),
            pitch_count=int(row.pitch_count),
            probability=float(row.pitch_count) / total,
        )
        for row in rows
    ]

    return total, probabilities


def predict_next_pitch_frequency(
    *,
    pitcher_id: int,
    balls: int,
    strikes: int,
    start_date: date,
    end_date: date,
    batter_id: int | None = None,
    batter_side: str | None = None,
    previous_pitch_type: str | None = None,
    minimum_sample: int = 20,
    top_n: int = 5,
) -> BaselinePrediction:
    """Predict next-pitch probabilities using hierarchical frequencies."""
    if balls not in {0, 1, 2, 3}:
        raise ValueError("balls must be between 0 and 3.")

    if strikes not in {0, 1, 2}:
        raise ValueError("strikes must be between 0 and 2.")

    if end_date < start_date:
        raise ValueError("end_date cannot be before start_date.")

    parameters = {
        "pitcher_id": pitcher_id,
        "balls": balls,
        "strikes": strikes,
        "batter_side": batter_side,
        "previous_pitch_type": previous_pitch_type,
        "start_date": start_date,
        "end_date": end_date,
    }

    query_levels = [
        (
            "pitcher-count-side-previous",
            QUERY_LEVEL_ONE,
        ),
        (
            "pitcher-count-side",
            QUERY_LEVEL_TWO,
        ),
        (
            "pitcher-count",
            QUERY_LEVEL_THREE,
        ),
        (
            "pitcher-overall",
            QUERY_LEVEL_FOUR,
        ),
        (
            "league-count-side",
            QUERY_LEAGUE_FALLBACK,
        ),
    ]

    chosen_level = "no-data"
    chosen_total = 0
    chosen_probabilities: list[PitchProbability] = []

    with session_scope() as session:
        for level_name, query in query_levels:
            rows = list(
                session.execute(
                    query,
                    parameters,
                ).all()
            )

            total, probabilities = rows_to_probabilities(rows)

            if total >= minimum_sample:
                chosen_level = level_name
                chosen_total = total
                chosen_probabilities = probabilities
                break

            if total > chosen_total:
                chosen_level = level_name
                chosen_total = total
                chosen_probabilities = probabilities

    return BaselinePrediction(
        pitcher_id=pitcher_id,
        batter_id=batter_id,
        balls=balls,
        strikes=strikes,
        batter_side=batter_side,
        previous_pitch_type=previous_pitch_type,
        sample_size=chosen_total,
        fallback_level=chosen_level,
        probabilities=chosen_probabilities[:top_n],
    )