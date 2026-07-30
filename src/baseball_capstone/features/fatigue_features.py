"""Pitcher workload and fatigue feature engineering."""

from __future__ import annotations

import pandas as pd


def add_fatigue_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Add in-game pitcher workload features."""
    required = {
        "pitcher_id",
        "game_pk",
        "at_bat_number",
        "pitch_number",
    }
    missing = required.difference(dataframe.columns)

    if missing:
        raise ValueError(
            "Missing fatigue columns: "
            + ", ".join(sorted(missing))
        )

    result = dataframe.copy()
    result = result.sort_values(
        [
            "game_pk",
            "pitcher_id",
            "at_bat_number",
            "pitch_number",
        ],
        kind="stable",
    )

    result["pitcher_game_pitch_number"] = (
        result.groupby(
            ["game_pk", "pitcher_id"],
            sort=False,
        )
        .cumcount()
        .add(1)
    )

    result["is_high_workload"] = (
        result["pitcher_game_pitch_number"] >= 80
    ).astype("int8")

    result["is_very_high_workload"] = (
        result["pitcher_game_pitch_number"] >= 100
    ).astype("int8")

    if "release_speed" in result.columns:
        first_twenty_velocity = (
            result[
                result["pitcher_game_pitch_number"] <= 20
            ]
            .groupby(
                ["game_pk", "pitcher_id"],
                sort=False,
            )["release_speed"]
            .mean()
            .rename("_game_initial_velocity")
        )

        result = result.join(
            first_twenty_velocity,
            on=["game_pk", "pitcher_id"],
        )

        result["velocity_drop_from_game_start"] = (
            result["_game_initial_velocity"]
            - result["release_speed"]
        )

        result = result.drop(
            columns=["_game_initial_velocity"]
        )

    return result
