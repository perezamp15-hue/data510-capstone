"""Batter tendency and rolling-form features."""

from __future__ import annotations

import pandas as pd


def add_batter_features(
    dataframe: pd.DataFrame,
    rolling_window: int = 100,
) -> pd.DataFrame:
    """Add leakage-safe rolling batter response features."""
    required = {
        "batter_id",
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
    }
    missing = required.difference(dataframe.columns)

    if missing:
        raise ValueError(
            "Missing batter columns: "
            + ", ".join(sorted(missing))
        )

    result = dataframe.copy()
    result = result.sort_values(
        [
            "batter_id",
            "game_date",
            "game_pk",
            "at_bat_number",
            "pitch_number",
        ],
        kind="stable",
    )

    batter_group = result.groupby(
        "batter_id",
        sort=False,
    )

    result["batter_prior_pitch_count"] = batter_group.cumcount()

    if "description" in result.columns:
        whiff = result["description"].isin(
            {
                "swinging_strike",
                "swinging_strike_blocked",
                "foul_tip",
            }
        ).astype(float)

        result["_batter_whiff_value"] = whiff

        result["batter_recent_whiff_rate"] = result.groupby(
            "batter_id",
            sort=False,
        )["_batter_whiff_value"].transform(
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
            columns=["_batter_whiff_value"]
        )

    if "is_strike" in result.columns:
        result["batter_recent_strike_rate"] = batter_group[
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

    if "is_in_play" in result.columns:
        result["batter_recent_in_play_rate"] = batter_group[
            "is_in_play"
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

    if "launch_speed" in result.columns:
        result["batter_recent_exit_velocity"] = batter_group[
            "launch_speed"
        ].transform(
            lambda series: (
                series.shift(1)
                .rolling(
                    rolling_window,
                    min_periods=5,
                )
                .mean()
            )
        )

    return result
