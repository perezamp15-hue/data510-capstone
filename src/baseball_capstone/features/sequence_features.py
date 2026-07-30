"""Pitch-sequence feature engineering."""

from __future__ import annotations
import numpy as np
import pandas as pd


SEQUENCE_SORT_COLUMNS = [
    "game_pk",
    "at_bat_number",
    "pitch_number",
]


def add_sequence_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Add prior-pitch and transition features.

    The dataframe must contain one row per pitch and must include:
    game_pk, at_bat_number, pitch_number, pitch_type, description,
    release_speed, plate_x, and plate_z.
    """
    required = {
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "pitch_type",
    }
    missing = required.difference(dataframe.columns)

    if missing:
        raise ValueError(
            "Missing sequence columns: "
            + ", ".join(sorted(missing))
        )

    result = dataframe.copy()
    result = result.sort_values(
        SEQUENCE_SORT_COLUMNS,
        kind="stable",
    )

    group_columns = ["game_pk", "at_bat_number"]
    grouped = result.groupby(group_columns, sort=False)

    for lag in range(1, 6):
        result[f"previous_{lag}_pitch_type"] = grouped[
            "pitch_type"
        ].shift(lag)

        if "description" in result.columns:
            result[f"previous_{lag}_description"] = grouped[
                "description"
            ].shift(lag)

        if "release_speed" in result.columns:
            result[f"previous_{lag}_velocity"] = grouped[
                "release_speed"
            ].shift(lag)

        if "plate_x" in result.columns:
            result[f"previous_{lag}_plate_x"] = grouped[
                "plate_x"
            ].shift(lag)

        if "plate_z" in result.columns:
            result[f"previous_{lag}_plate_z"] = grouped[
                "plate_z"
            ].shift(lag)

    result["same_as_previous_pitch"] = (
        result["pitch_type"]
        == result["previous_1_pitch_type"]
    ).astype("int8")

    if "release_speed" in result.columns:
        result["velocity_change_from_previous"] = (
            result["release_speed"]
            - result["previous_1_velocity"]
        )

    if {"plate_x", "plate_z"}.issubset(result.columns):
        dx = (
            result["plate_x"].astype(float)
            - result["previous_1_plate_x"].astype(float)
        )

        dz = (
            result["plate_z"].astype(float)
            - result["previous_1_plate_z"].astype(float)
        )

        result["location_change_from_previous"] = np.sqrt(
            dx**2 + dz**2
        )

    return result
