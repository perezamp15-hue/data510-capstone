from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd

SWING_EVENTS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}

WHIFF_EVENTS = {
    "swinging_strike",
    "swinging_strike_blocked",
}

CALLED_STRIKE_EVENTS = {
    "called_strike",
}

STRIKE_EVENTS = {
    "called_strike",
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}

BALL_EVENTS = {
    "ball",
    "blocked_ball",
    "pitchout",
    "intent_ball",
    "hit_by_pitch",
}

def safe_percentage(
    numerator: int | float,
    denominator: int | float,
    decimals: int = 1,
) -> float:
    """
    Safely calculate a percentage.

    Returns 0.0 when the denominator is zero.
    """
    if denominator in (0, None) or pd.isna(denominator):
        return 0.0

    return round((numerator / denominator) * 100, decimals)

def safe_mean(
    series: pd.Series,
    decimals: int = 1,
) -> float | None:
    """
    Safely calculate a numeric mean.
    """
    numeric = pd.to_numeric(series, errors="coerce").dropna()

    if numeric.empty:
        return None

    return round(float(numeric.mean()), decimals)


def normalize_event(value: Any) -> str:
    """
    Normalize pitch descriptions and play events.
    """
    if value is None or pd.isna(value):
        return ""

    return str(value).strip().lower()


def add_pitch_flags(pitches: pd.DataFrame) -> pd.DataFrame:
    """
    Add reusable Boolean flags to pitch-level data.
    """
    frame = pitches.copy()

    if frame.empty:
        return frame

    frame["normalized_description"] = (
        frame["pitch_description"]
        .apply(normalize_event)
    )

    frame["normalized_event"] = (
        frame["play_event"]
        .apply(normalize_event)
    )

    frame["is_swing"] = frame["normalized_description"].isin(
        SWING_EVENTS
    )

    frame["is_whiff"] = frame["normalized_description"].isin(
        WHIFF_EVENTS
    )

    frame["is_called_strike"] = (
        frame["normalized_description"].isin(
            CALLED_STRIKE_EVENTS
        )
    )

    frame["is_strike"] = frame["normalized_description"].isin(
        STRIKE_EVENTS
    )

    frame["is_ball"] = frame["normalized_description"].isin(
        BALL_EVENTS
    )

    frame["is_csw"] = (
        frame["is_called_strike"]
        | frame["is_whiff"]
    )

    frame["is_in_zone"] = (
        frame["plate_crossing_x"].between(
            -0.83,
            0.83,
            inclusive="both",
        )
        & frame["plate_crossing_z"].between(
            frame["sz_bot"],
            frame["sz_top"],
            inclusive="both",
        )
    )

    frame["is_chase"] = (
        frame["is_swing"]
        & ~frame["is_in_zone"]
    )

    frame["is_contact"] = (
        frame["is_swing"]
        & ~frame["is_whiff"]
    )

    return frame


def calculate_pitcher_summary(
    pitches: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calculate overall pitcher metrics from pitch-level data.
    """
    if pitches.empty:
        return {
            "pitch_count": 0,
            "game_count": 0,
            "batter_count": 0,
            "plate_appearances": 0,
            "strike_rate": 0.0,
            "swing_rate": 0.0,
            "whiff_rate": 0.0,
            "csw_rate": 0.0,
            "zone_rate": 0.0,
            "chase_rate": 0.0,
            "contact_rate": 0.0,
            "average_velocity": None,
            "average_spin_rate": None,
            "average_extension": None,
            "average_exit_velocity": None,
            "hard_hit_rate": 0.0,
            "sweet_spot_rate": 0.0,
            "expected_woba_allowed": None,
            "expected_slugging_allowed": None,
        }

    frame = add_pitch_flags(pitches)

    pitch_count = len(frame)
    swing_count = int(frame["is_swing"].sum())
    whiff_count = int(frame["is_whiff"].sum())
    strike_count = int(frame["is_strike"].sum())
    csw_count = int(frame["is_csw"].sum())
    zone_count = int(frame["is_in_zone"].sum())
    chase_count = int(frame["is_chase"].sum())
    contact_count = int(frame["is_contact"].sum())

    out_of_zone_swings = frame.loc[
        ~frame["is_in_zone"],
        "is_swing",
    ]

    batted_balls = frame.loc[
        frame["exit_velocity"].notna()
    ]

    hard_hit_count = 0
    sweet_spot_count = 0

    if not batted_balls.empty:
        hard_hit_count = int(
            batted_balls["is_hard_hit"]
            .fillna(False)
            .astype(bool)
            .sum()
        )

        sweet_spot_count = int(
            batted_balls["is_sweet_spot"]
            .fillna(False)
            .astype(bool)
            .sum()
        )

    return {
        "pitch_count": pitch_count,
        "game_count": int(frame["game_pk"].nunique()),
        "batter_count": int(frame["batter_id"].nunique()),
        "plate_appearances": int(
            frame[
                [
                    "game_pk",
                    "plate_appearance_number",
                ]
            ]
            .drop_duplicates()
            .shape[0]
        ),
        "strike_rate": safe_percentage(
            strike_count,
            pitch_count,
        ),
        "swing_rate": safe_percentage(
            swing_count,
            pitch_count,
        ),
        "whiff_rate": safe_percentage(
            whiff_count,
            swing_count,
        ),
        "csw_rate": safe_percentage(
            csw_count,
            pitch_count,
        ),
        "zone_rate": safe_percentage(
            zone_count,
            pitch_count,
        ),
        "chase_rate": safe_percentage(
            chase_count,
            len(out_of_zone_swings),
        ),
        "contact_rate": safe_percentage(
            contact_count,
            swing_count,
        ),
        "average_velocity": safe_mean(
            frame["release_velocity"]
        ),
        "average_spin_rate": safe_mean(
            frame["release_spin_rate"],
            decimals=0,
        ),
        "average_extension": safe_mean(
            frame["release_extension"]
        ),
        "average_exit_velocity": safe_mean(
            batted_balls["exit_velocity"]
            if not batted_balls.empty
            else pd.Series(dtype=float)
        ),
        "hard_hit_rate": safe_percentage(
            hard_hit_count,
            len(batted_balls),
        ),
        "sweet_spot_rate": safe_percentage(
            sweet_spot_count,
            len(batted_balls),
        ),
        "expected_woba_allowed": safe_mean(
            frame["expected_woba"],
            decimals=3,
        ),
        "expected_slugging_allowed": safe_mean(
            frame["expected_slugging"],
            decimals=3,
        ),
    }


def calculate_pitch_arsenal(
    pitches: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Calculate metrics grouped by pitch type.
    """
    if pitches.empty:
        return []

    frame = add_pitch_flags(pitches)

    valid_pitches = frame.loc[
        frame["pitch_type"].notna()
    ].copy()

    if valid_pitches.empty:
        return []

    total_pitches = len(valid_pitches)
    arsenal: list[dict[str, Any]] = []

    grouped = valid_pitches.groupby(
        "pitch_type",
        dropna=False,
    )

    for pitch_type, group in grouped:
        pitch_count = len(group)
        swing_count = int(group["is_swing"].sum())
        whiff_count = int(group["is_whiff"].sum())
        strike_count = int(group["is_strike"].sum())
        csw_count = int(group["is_csw"].sum())
        zone_count = int(group["is_in_zone"].sum())
        chase_count = int(group["is_chase"].sum())

        out_of_zone_count = int(
            (~group["is_in_zone"]).sum()
        )

        batted_balls = group.loc[
            group["exit_velocity"].notna()
        ]

        hard_hit_count = int(
            batted_balls["is_hard_hit"]
            .fillna(False)
            .astype(bool)
            .sum()
        )

        arsenal.append(
            {
                "pitch_type": str(pitch_type),
                "pitch_count": pitch_count,
                "usage_percent": safe_percentage(
                    pitch_count,
                    total_pitches,
                ),
                "average_velocity": safe_mean(
                    group["release_velocity"]
                ),
                "maximum_velocity": (
                    round(
                        float(
                            pd.to_numeric(
                                group["release_velocity"],
                                errors="coerce",
                            ).max()
                        ),
                        1,
                    )
                    if group["release_velocity"]
                    .notna()
                    .any()
                    else None
                ),
                "average_spin_rate": safe_mean(
                    group["release_spin_rate"],
                    decimals=0,
                ),
                "average_extension": safe_mean(
                    group["release_extension"]
                ),
                "strike_rate": safe_percentage(
                    strike_count,
                    pitch_count,
                ),
                "zone_rate": safe_percentage(
                    zone_count,
                    pitch_count,
                ),
                "swing_rate": safe_percentage(
                    swing_count,
                    pitch_count,
                ),
                "whiff_rate": safe_percentage(
                    whiff_count,
                    swing_count,
                ),
                "csw_rate": safe_percentage(
                    csw_count,
                    pitch_count,
                ),
                "chase_rate": safe_percentage(
                    chase_count,
                    out_of_zone_count,
                ),
                "average_exit_velocity": safe_mean(
                    batted_balls["exit_velocity"]
                ),
                "hard_hit_rate": safe_percentage(
                    hard_hit_count,
                    len(batted_balls),
                ),
                "expected_woba_allowed": safe_mean(
                    group["expected_woba"],
                    decimals=3,
                ),
                "expected_slugging_allowed": safe_mean(
                    group["expected_slugging"],
                    decimals=3,
                ),
            }
        )

    arsenal.sort(
        key=lambda item: item["pitch_count"],
        reverse=True,
    )

    return arsenal


def calculate_velocity_distribution(
    pitches: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Return velocity percentiles by pitch type.
    """
    if pitches.empty:
        return []

    frame = pitches.copy()

    frame["release_velocity"] = pd.to_numeric(
        frame["release_velocity"],
        errors="coerce",
    )

    frame = frame.loc[
        frame["pitch_type"].notna()
        & frame["release_velocity"].notna()
    ]

    if frame.empty:
        return []

    results: list[dict[str, Any]] = []

    for pitch_type, group in frame.groupby("pitch_type"):
        velocity = group["release_velocity"]

        results.append(
            {
                "pitch_type": str(pitch_type),
                "minimum": round(float(velocity.min()), 1),
                "percentile_25": round(
                    float(np.percentile(velocity, 25)),
                    1,
                ),
                "median": round(
                    float(np.percentile(velocity, 50)),
                    1,
                ),
                "percentile_75": round(
                    float(np.percentile(velocity, 75)),
                    1,
                ),
                "maximum": round(float(velocity.max()), 1),
            }
        )

    return results 