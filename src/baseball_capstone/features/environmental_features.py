"""Environmental and park-context feature engineering."""

from __future__ import annotations

import pandas as pd


def add_environmental_features(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize available weather and park features.

    Missing optional environmental fields are created as nulls so
    downstream model code can use a stable schema.
    """
    result = dataframe.copy()

    optional_columns = {
        "temperature_f": pd.NA,
        "wind_speed_mph": pd.NA,
        "wind_direction": pd.NA,
        "weather_condition": pd.NA,
        "park_id": pd.NA,
        "day_night": pd.NA,
    }

    for column, default_value in optional_columns.items():
        if column not in result.columns:
            result[column] = default_value

    if "temperature_f" in result.columns:
        result["is_cold_weather"] = (
            pd.to_numeric(
                result["temperature_f"],
                errors="coerce",
            )
            < 55
        ).astype("int8")

        result["is_hot_weather"] = (
            pd.to_numeric(
                result["temperature_f"],
                errors="coerce",
            )
            >= 85
        ).astype("int8")

    return result
