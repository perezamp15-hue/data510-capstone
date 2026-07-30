"""Pitcher-batter matchup feature engineering."""

from __future__ import annotations

import pandas as pd


def add_matchup_features(
    dataframe: pd.DataFrame,
    rolling_window: int = 50,
) -> pd.DataFrame:
    """Add historical pitcher-vs-batter features."""
    required = {
        "pitcher_id",
        "batter_id",
        "game_date",
        "game_pk",
        "at_bat_number",
        "pitch_number",
    }
    missing = required.difference(dataframe.columns)

    if missing:
        raise ValueError(
            "Missing matchup columns: "
            + ", ".join(sorted(missing))
        )

    result = dataframe.copy()
    result = result.sort_values(
        [
            "pitcher_id",
            "batter_id",
            "game_date",
            "game_pk",
            "at_bat_number",
            "pitch_number",
        ],
        kind="stable",
    )

    matchup_columns = ["pitcher_id", "batter_id"]
    matchup_group = result.groupby(
        matchup_columns,
        sort=False,
    )

    result["matchup_prior_pitch_count"] = matchup_group.cumcount()

    if "is_strike" in result.columns:
        result["matchup_recent_strike_rate"] = matchup_group[
            "is_strike"
        ].transform(
            lambda series: (
                series.astype(float)
                .shift(1)
                .rolling(
                    rolling_window,
                    min_periods=5,
                )
                .mean()
            )
        )

    if "description" in result.columns:
        whiff = result["description"].isin(
            {
                "swinging_strike",
                "swinging_strike_blocked",
                "foul_tip",
            }
        ).astype(float)

        result["_matchup_whiff_value"] = whiff

        result["matchup_recent_whiff_rate"] = result.groupby(
            matchup_columns,
            sort=False,
        )["_matchup_whiff_value"].transform(
            lambda series: (
                series.shift(1)
                .rolling(
                    rolling_window,
                    min_periods=5,
                )
                .mean()
            )
        )

        result = result.drop(
            columns=["_matchup_whiff_value"]
        )

    if {"pitcher_hand", "batter_side"}.issubset(result.columns):
        result["has_platoon_advantage"] = (
            result["pitcher_hand"]
            == result["batter_side"]
        ).astype("int8")

    return result
