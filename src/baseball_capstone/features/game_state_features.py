"""Game-state feature engineering."""

from __future__ import annotations

import pandas as pd


def add_game_state_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Add inning, score, outs, and base-state features."""
    result = dataframe.copy()

    for column in (
        "runner_on_first",
        "runner_on_second",
        "runner_on_third",
    ):
        if column not in result.columns:
            result[column] = False

        result[column] = (
            result[column]
            .fillna(False)
            .astype("int8")
        )

    result["runners_on_base"] = (
        result["runner_on_first"]
        + result["runner_on_second"]
        + result["runner_on_third"]
    ).astype("int8")

    result["has_runner_in_scoring_position"] = (
        (
            result["runner_on_second"] == 1
        )
        | (
            result["runner_on_third"] == 1
        )
    ).astype("int8")

    if {"home_score", "away_score"}.issubset(result.columns):
        home_batting = (
            result.get("inning_half", "")
            .astype(str)
            .str.lower()
            .eq("bottom")
        )

        batting_score = result["away_score"].where(
            ~home_batting,
            result["home_score"],
        )
        fielding_score = result["home_score"].where(
            ~home_batting,
            result["away_score"],
        )

        result["batting_score_differential"] = (
            batting_score - fielding_score
        )

        result["is_tie_game"] = (
            result["batting_score_differential"] == 0
        ).astype("int8")

    if "inning" in result.columns:
        result["is_late_inning"] = (
            result["inning"] >= 7
        ).astype("int8")

        result["is_extra_inning"] = (
            result["inning"] >= 10
        ).astype("int8")

    return result
