"""Pitcher tendency and rolling-form features."""

from __future__ import annotations

import pandas as pd


def add_pitcher_features(
    dataframe: pd.DataFrame,
    rolling_window: int = 100,
) -> pd.DataFrame:
    """Add leakage-safe rolling pitcher tendencies.

    Rolling values are shifted by one pitch so the current pitch
    is not included in its own predictors.
    """
    required = {
        "pitcher_id",
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
        "pitch_type",
    }
    missing = required.difference(dataframe.columns)

    if missing:
        raise ValueError(
            "Missing pitcher columns: "
            + ", ".join(sorted(missing))
        )

    result = dataframe.copy()
    result = result.sort_values(
        [
            "pitcher_id",
            "game_date",
            "game_pk",
            "at_bat_number",
            "pitch_number",
        ],
        kind="stable",
    )

    pitcher_group = result.groupby(
        "pitcher_id",
        sort=False,
    )

    result["pitcher_prior_pitch_count"] = pitcher_group.cumcount()

    if "release_speed" in result.columns:
        result["pitcher_recent_velocity"] = pitcher_group[
            "release_speed"
        ].transform(
            lambda series: (
                series.shift(1)
                .rolling(
                    rolling_window,
                    min_periods=10,
                )
                .mean()
            )
        )

    if "is_strike" in result.columns:
        result["pitcher_recent_strike_rate"] = pitcher_group[
            "is_strike"
        ].transform(
            lambda series: (
                series.astype(float)
                .shift(1)
                .rolling(
                    rolling_window,
                    min_periods=10,
                )
                .mean()
            )
        )

    if "description" in result.columns:
        whiff_values = result["description"].isin(
            {
                "swinging_strike",
                "swinging_strike_blocked",
                "foul_tip",
            }
        ).astype(float)

        result["_pitcher_whiff_value"] = whiff_values

        result["pitcher_recent_whiff_rate"] = result.groupby(
            "pitcher_id",
            sort=False,
        )["_pitcher_whiff_value"].transform(
            lambda series: (
                series.shift(1)
                .rolling(
                    rolling_window,
                    min_periods=10,
                )
                .mean()
            )
        )

        result = result.drop(
            columns=["_pitcher_whiff_value"]
        )

    pitch_type_history = pd.get_dummies(
        result["pitch_type"],
        prefix="pitcher_usage",
        dtype=float,
    )

    for column in pitch_type_history.columns:
        result[column] = pitch_type_history[column]

        result[f"{column}_rolling"] = result.groupby(
            "pitcher_id",
            sort=False,
        )[column].transform(
            lambda series: (
                series.shift(1)
                .rolling(
                    rolling_window,
                    min_periods=10,
                )
                .mean()
            )
        )

        result = result.drop(columns=[column])

    return result
