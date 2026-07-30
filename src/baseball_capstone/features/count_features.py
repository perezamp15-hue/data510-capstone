"""Count-state feature engineering."""

from __future__ import annotations

import pandas as pd


def add_count_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Add count-based flags used by pitch prediction models."""
    required = {"balls", "strikes"}
    missing = required.difference(dataframe.columns)

    if missing:
        raise ValueError(
            "Missing count columns: "
            + ", ".join(sorted(missing))
        )

    result = dataframe.copy()

    result["is_first_pitch"] = (
        (result["balls"] == 0)
        & (result["strikes"] == 0)
    ).astype("int8")

    result["is_two_strike_count"] = (
        result["strikes"] == 2
    ).astype("int8")

    result["is_full_count"] = (
        (result["balls"] == 3)
        & (result["strikes"] == 2)
    ).astype("int8")

    result["is_pitcher_count"] = (
        result["strikes"] > result["balls"]
    ).astype("int8")

    result["is_hitter_count"] = (
        result["balls"] > result["strikes"]
    ).astype("int8")

    result["count_code"] = (
        result["balls"].astype("Int64").astype(str)
        + "-"
        + result["strikes"].astype("Int64").astype(str)
    )

    return result
