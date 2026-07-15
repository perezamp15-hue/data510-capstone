from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from db_client import get_engine
from visualizations.pitch_location_movement import (
    add_movement_to_arsenal_table,
    calculate_pitch_movement,
    movement_summary_to_records,
    prepare_location_data,
    summarize_pitch_movement,
)
from visualizations.pitcher_report_card import (
    create_pitcher_report_card,
)

DEFAULT_OUTPUT_DIRECTORY = Path("output")

PITCH_NAMES = {
    "FF": "4-Seam",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Forkball",
    "SC": "Screwball",
    "KN": "Knuckleball",
    "EP": "Eephus",
}

STRIKE_DESCRIPTIONS = {
    "called_strike",
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}

SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}

WHIFF_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
}

CONTACT_DESCRIPTIONS = {
    "foul",
    "foul_tip",
    "foul_bunt",
    "hit_into_play",
}

CSW_DESCRIPTIONS = {
    "called_strike",
    "swinging_strike",
    "swinging_strike_blocked",
}

BALL_DESCRIPTIONS = {
    "ball",
    "blocked_ball",
    "pitchout",
}

TERMINAL_STRIKEOUT_EVENTS = {
    "strikeout",
    "strikeout_double_play",
}

TERMINAL_WALK_EVENTS = {
    "walk",
    "intent_walk",
}

PITCHER_PITCHES_QUERY = """
SELECT
    sp.pitch_id,
    sp.game_pk,
    sp.game_date,
    sp.pitcher_id,
    sp.batter_id,

    sp.at_bat_number,
    sp.plate_appearance_number,
    sp.pitch_number,
    sp.inning,
    sp.inning_half,
    sp.outs,

    sp.ball_count,
    sp.strike_count,

    sp.pitch_type,
    sp.pitch_description,

    sp.release_velocity,
    sp.release_spin_rate,
    sp.release_extension,

    sp.release_pos_x,
    sp.release_pos_y,
    sp.release_pos_z,

    sp.vx0,
    sp.vy0,
    sp.vz0,

    sp.ax,
    sp.ay,
    sp.az,

    sp.plate_crossing_x,
    sp.plate_crossing_z,

    sp.sz_top,
    sp.sz_bot AS sz_bottom,

    sp.effective_speed,

    sp.runner_on_first,
    sp.runner_on_second,
    sp.runner_on_third,

    sp.home_score,
    sp.away_score,

    sp.exit_velocity AS launch_speed,
    sp.launch_angle,

    sp.expected_woba
        AS estimated_woba_using_speedangle,

    sp.expected_slugging
        AS estimated_slg_using_speedangle,

    sp.play_event AS events,

    batter.bats AS stand,

    sp.is_hard_hit AS database_is_hard_hit,
    sp.is_sweet_spot AS database_is_sweet_spot

FROM public.statcast_pitches AS sp

LEFT JOIN public.players AS batter
    ON batter.player_id = sp.batter_id

WHERE sp.pitcher_id = :pitcher_id
  AND EXTRACT(YEAR FROM sp.game_date) = :season
  AND sp.pitch_type IS NOT NULL

ORDER BY
    sp.game_date,
    sp.game_pk,
    sp.at_bat_number,
    sp.pitch_number
"""


def load_pitcher_metadata(
    pitcher_id: int,
) -> dict[str, Any]:
    """
    Load pitcher metadata from public.players.

    The report can still run when the player record is
    missing or when the metadata query fails.
    """
    engine = get_engine()

    metadata: dict[str, Any] = {
        "pitcher_name": f"Pitcher {pitcher_id}",
        "team_name": "",
        "throws": "",
    }

    query = """
    SELECT
        full_name,
        throws
    FROM public.players
    WHERE player_id = :pitcher_id
    LIMIT 1
    """

    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(query),
                {
                    "pitcher_id": pitcher_id,
                },
            ).mappings().first()

    except SQLAlchemyError as exc:
        print(
            "Warning: pitcher metadata could not be loaded. "
            f"{exc}"
        )
        return metadata

    if not row:
        return metadata

    full_name = row.get("full_name")

    if full_name:
        metadata["pitcher_name"] = str(
            full_name
        ).strip()

    throwing_hand = row.get("throws")

    if throwing_hand:
        normalized_hand = (
            str(throwing_hand)
            .strip()
            .upper()
        )

        if normalized_hand in {
            "R",
            "RIGHT",
            "RHP",
        }:
            metadata["throws"] = "RHP"

        elif normalized_hand in {
            "L",
            "LEFT",
            "LHP",
        }:
            metadata["throws"] = "LHP"

        else:
            metadata["throws"] = normalized_hand

    return metadata


def load_pitcher_metadata(
    pitcher_id: int,
) -> dict[str, Any]:
    """
    Load pitcher name and throwing hand from public.players.

    The function uses multiple queries so the report can still run
    when the players table does not contain every optional column.
    """
    engine = get_engine()

    metadata: dict[str, Any] = {
        "pitcher_name": f"Pitcher {pitcher_id}",
        "team_name": "",
        "throws": "",
    }

    queries = [
        """
        SELECT
            full_name,
            throws
        FROM public.players
        WHERE player_id = :pitcher_id
        LIMIT 1
        """,
        """
        SELECT
            full_name
        FROM public.players
        WHERE player_id = :pitcher_id
        LIMIT 1
        """,
    ]

    for query in queries:
        try:
            with engine.connect() as connection:
                row = connection.execute(
                    text(query),
                    {
                        "pitcher_id": pitcher_id,
                    },
                ).mappings().first()

            if not row:
                continue

            full_name = row.get(
                "full_name"
            )

            if full_name:
                metadata["pitcher_name"] = str(
                    full_name
                )

            throwing_hand = row.get(
                "throws"
            )

            if throwing_hand:
                throwing_hand_text = (
                    str(throwing_hand)
                    .strip()
                    .upper()
                )

                if throwing_hand_text in {
                    "R",
                    "RIGHT",
                    "RHP",
                }:
                    metadata["throws"] = "RHP"

                elif throwing_hand_text in {
                    "L",
                    "LEFT",
                    "LHP",
                }:
                    metadata["throws"] = "LHP"

                else:
                    metadata["throws"] = (
                        throwing_hand_text
                    )

            break

        except SQLAlchemyError:
            continue

    return metadata


def add_pitch_flags(
    pitches: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add pitch-result, zone, swing, contact, and batted-ball
    flags to the pitch-level DataFrame.
    """
    dataframe = pitches.copy()

    descriptions = normalized_text_column(
        dataframe,
        "pitch_description",
    )

    events = normalized_text_column(
        dataframe,
        "events",
    )

    dataframe["is_strike"] = descriptions.isin(
        STRIKE_DESCRIPTIONS
    )

    dataframe["is_swing"] = descriptions.isin(
        SWING_DESCRIPTIONS
    )

    dataframe["is_whiff"] = descriptions.isin(
        WHIFF_DESCRIPTIONS
    )

    dataframe["is_contact"] = descriptions.isin(
        CONTACT_DESCRIPTIONS
    )

    dataframe["is_csw"] = descriptions.isin(
        CSW_DESCRIPTIONS
    )

    dataframe["is_ball"] = descriptions.isin(
        BALL_DESCRIPTIONS
    )

    dataframe["is_called_strike"] = (
        descriptions == "called_strike"
    )

    dataframe["is_in_play"] = (
        descriptions == "hit_into_play"
    )

    dataframe["is_strikeout_event"] = events.isin(
        TERMINAL_STRIKEOUT_EVENTS
    )

    dataframe["is_walk_event"] = events.isin(
        TERMINAL_WALK_EVENTS
    )

    plate_x = numeric_column(
        dataframe,
        "plate_crossing_x",
    )

    plate_z = numeric_column(
        dataframe,
        "plate_crossing_z",
    )

    zone_top = numeric_column(
        dataframe,
        "sz_top",
    )

    zone_bottom = numeric_column(
        dataframe,
        "sz_bottom",
    )

    valid_zone = (
        plate_x.notna()
        & plate_z.notna()
        & zone_top.notna()
        & zone_bottom.notna()
        & (zone_top > zone_bottom)
    )

    dataframe["has_valid_zone"] = valid_zone

    dataframe["is_in_zone"] = (
        valid_zone
        & plate_x.between(
            -17.0 / 24.0,
            17.0 / 24.0,
            inclusive="both",
        )
        & plate_z.between(
            zone_bottom,
            zone_top,
            inclusive="both",
        )
    )

    dataframe["is_out_of_zone"] = (
        valid_zone
        & ~dataframe["is_in_zone"]
    )

    dataframe["is_chase"] = (
        dataframe["is_swing"]
        & dataframe["is_out_of_zone"]
    )

    launch_speed = numeric_column(
        dataframe,
        "launch_speed",
    )

    launch_angle = numeric_column(
        dataframe,
        "launch_angle",
    )

    dataframe["is_batted_ball"] = (
        dataframe["is_in_play"]
        & launch_speed.notna()
    )

    calculated_hard_hit = (
        dataframe["is_batted_ball"]
        & launch_speed.ge(95.0)
    )

    if "database_is_hard_hit" in dataframe.columns:
        stored_hard_hit = (
            dataframe["database_is_hard_hit"]
            .astype("boolean")
        )

        dataframe["is_hard_hit"] = (
            stored_hard_hit
            .where(
                stored_hard_hit.notna(),
                calculated_hard_hit,
            )
            .fillna(False)
            .astype(bool)
        )

        dataframe["is_hard_hit"] = (
            dataframe["is_batted_ball"]
            & dataframe["is_hard_hit"]
        )

    else:
        dataframe["is_hard_hit"] = (
            calculated_hard_hit
        )

    calculated_sweet_spot = (
        dataframe["is_batted_ball"]
        & launch_angle.between(
            8.0,
            32.0,
            inclusive="both",
        )
    )

    if "database_is_sweet_spot" in dataframe.columns:
        stored_sweet_spot = (
            dataframe["database_is_sweet_spot"]
            .astype("boolean")
        )

        dataframe["is_sweet_spot"] = (
            stored_sweet_spot
            .where(
                stored_sweet_spot.notna(),
                calculated_sweet_spot,
            )
            .fillna(False)
            .astype(bool)
        )

        dataframe["is_sweet_spot"] = (
            dataframe["is_batted_ball"]
            & dataframe["is_sweet_spot"]
        )

    else:
        dataframe["is_sweet_spot"] = (
            calculated_sweet_spot
        )

    return dataframe

def get_valid_batted_balls(
    pitches: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return only balls in play with a valid exit velocity.

    Every overall, pitch-type, and handedness hard-hit
    calculation should use this same population.
    """
    if pitches.empty:
        return pitches.iloc[0:0].copy()

    launch_speed = numeric_column(
        pitches,
        "launch_speed",
    )

    if "is_batted_ball" in pitches.columns:
        batted_ball_mask = (
            pitches["is_batted_ball"]
            .fillna(False)
            .astype(bool)
        )

    else:
        descriptions = normalized_text_column(
            pitches,
            "pitch_description",
        )

        batted_ball_mask = (
            descriptions == "hit_into_play"
        )

    valid_mask = (
        batted_ball_mask
        & launch_speed.notna()
    )

    return pitches.loc[
        valid_mask
    ].copy()

def safe_float(
    value: Any,
    default: float | None = None,
) -> float | None:
    try:
        number = float(value)

        if math.isfinite(number):
            return number

    except (TypeError, ValueError):
        pass

    return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    number = safe_float(value)

    if number is None:
        return default

    return int(round(number))


def round_or_none(
    value: Any,
    decimals: int = 1,
) -> float | None:
    number = safe_float(value)

    if number is None:
        return None

    return round(number, decimals)


def percentage(
    numerator: Any,
    denominator: Any,
    decimals: int = 1,
) -> float | None:
    numerator_value = safe_float(numerator)
    denominator_value = safe_float(denominator)

    if (
        numerator_value is None
        or denominator_value is None
        or denominator_value <= 0
    ):
        return None

    return round(
        numerator_value / denominator_value * 100.0,
        decimals,
    )


def numeric_column(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(
            np.nan,
            index=dataframe.index,
            dtype="float64",
        )

    return pd.to_numeric(
        dataframe[column],
        errors="coerce",
    )


def normalized_text_column(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    if column not in dataframe.columns:
        return pd.Series(
            "",
            index=dataframe.index,
            dtype="object",
        )

    return (
        dataframe[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )


def clean_json_value(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {
            str(key): clean_json_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            clean_json_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            clean_json_value(item)
            for item in value
        ]

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None

        return float(value)

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

    if pd.isna(value):
        return None

    return value


def load_pitcher_pitches(
    pitcher_id: int,
    season: int | None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    engine = get_engine()

    print(
        f"Loading pitches for pitcher {pitcher_id}, "
        f"season {season}..."
    )

    with engine.connect() as connection:
        pitches = pd.read_sql(
            text(PITCHER_PITCHES_QUERY),
            connection,
            params={
                "pitcher_id": pitcher_id,
                "season": season,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    print(f"Loaded {len(pitches):,} pitches.")

    if pitches.empty:
        raise RuntimeError(
            f"No pitches were found for pitcher {pitcher_id} "
            f"during season {season}."
        )

    return pitches

def load_pitcher_metadata(
    pitcher_id: int,
) -> dict[str, Any]:
    """
    Attempts to load the pitcher's name from public.players.

    The report still runs if the players query fails.
    """
    engine = get_engine()

    metadata = {
        "pitcher_name": f"Pitcher {pitcher_id}",
        "team_name": "",
        "throws": "",
    }

    queries = [
        """
        SELECT
            full_name,
            pitch_hand
        FROM public.players
        WHERE player_id = :pitcher_id
        LIMIT 1
        """,
        """
        SELECT
            full_name
        FROM public.players
        WHERE player_id = :pitcher_id
        LIMIT 1
        """,
    ]

    for query in queries:
        try:
            with engine.connect() as connection:
                row = connection.execute(
                    text(query),
                    {
                        "pitcher_id": pitcher_id,
                    },
                ).mappings().first()

            if not row:
                continue

            full_name = row.get("full_name")

            if full_name:
                metadata["pitcher_name"] = str(
                    full_name
                )

            pitch_hand = row.get("pitch_hand")

            if pitch_hand:
                pitch_hand_text = str(
                    pitch_hand
                ).upper()

                if pitch_hand_text in {
                    "R",
                    "RIGHT",
                }:
                    metadata["throws"] = "RHP"

                elif pitch_hand_text in {
                    "L",
                    "LEFT",
                }:
                    metadata["throws"] = "LHP"

                else:
                    metadata["throws"] = pitch_hand_text

            break

        except SQLAlchemyError:
            continue

    return metadata


def add_pitch_flags(
    pitches: pd.DataFrame,
) -> pd.DataFrame:
    dataframe = pitches.copy()

    descriptions = normalized_text_column(
        dataframe,
        "pitch_description",
    )

    events = normalized_text_column(
        dataframe,
        "events",
    )

    dataframe["is_strike"] = descriptions.isin(
        STRIKE_DESCRIPTIONS
    )

    dataframe["is_swing"] = descriptions.isin(
        SWING_DESCRIPTIONS
    )

    dataframe["is_whiff"] = descriptions.isin(
        WHIFF_DESCRIPTIONS
    )

    dataframe["is_contact"] = descriptions.isin(
        CONTACT_DESCRIPTIONS
    )

    dataframe["is_csw"] = descriptions.isin(
        CSW_DESCRIPTIONS
    )

    dataframe["is_ball"] = descriptions.isin(
        BALL_DESCRIPTIONS
    )

    dataframe["is_called_strike"] = (
        descriptions == "called_strike"
    )

    dataframe["is_in_play"] = (
        descriptions == "hit_into_play"
    )

    dataframe["is_strikeout_event"] = events.isin(
        TERMINAL_STRIKEOUT_EVENTS
    )

    dataframe["is_walk_event"] = events.isin(
        TERMINAL_WALK_EVENTS
    )

    plate_x = numeric_column(
        dataframe,
        "plate_crossing_x",
    )

    plate_z = numeric_column(
        dataframe,
        "plate_crossing_z",
    )

    zone_top = numeric_column(
        dataframe,
        "sz_top",
    )

    zone_bottom = numeric_column(
        dataframe,
        "sz_bottom",
    )

    valid_zone = (
        plate_x.notna()
        & plate_z.notna()
        & zone_top.notna()
        & zone_bottom.notna()
    )

    dataframe["is_in_zone"] = (
        valid_zone
        & plate_x.between(
            -17.0 / 24.0,
            17.0 / 24.0,
        )
        & (plate_z >= zone_bottom)
        & (plate_z <= zone_top)
    )

    dataframe["is_out_of_zone"] = (
        valid_zone
        & ~dataframe["is_in_zone"]
    )

    dataframe["is_chase"] = (
        dataframe["is_swing"]
        & dataframe["is_out_of_zone"]
    )

    launch_speed = numeric_column(
        dataframe,
        "launch_speed",
    )

    launch_angle = numeric_column(
        dataframe,
        "launch_angle",
    )

    dataframe["is_batted_ball"] = (
        dataframe["is_in_play"]
        & launch_speed.notna()
    )

    dataframe["is_hard_hit"] = (
        dataframe["is_batted_ball"]
        & (launch_speed >= 95.0)
    )

    dataframe["is_sweet_spot"] = (
        dataframe["is_batted_ball"]
        & launch_angle.between(
            8.0,
            32.0,
        )
    )

    return dataframe

def plate_appearance_key_columns(
    pitches: pd.DataFrame,
) -> list[str]:
    candidates = [
        "game_pk",
        "at_bat_number",
    ]

    if all(
        column in pitches.columns
        for column in candidates
    ):
        return candidates

    candidates = [
        "game_pk",
        "plate_appearance_number",
    ]

    if all(
        column in pitches.columns
        for column in candidates
    ):
        return candidates

    return [
        "game_pk",
        "batter_id",
        "inning",
        "inning_half",
    ]


def get_terminal_plate_appearances(
    pitches: pd.DataFrame,
) -> pd.DataFrame:
    key_columns = plate_appearance_key_columns(
        pitches
    )

    sort_columns = [
        column
        for column in [
            "game_date",
            "game_pk",
            "at_bat_number",
            "plate_appearance_number",
            "pitch_number",
        ]
        if column in pitches.columns
    ]

    ordered = pitches.sort_values(
        sort_columns
    ).copy()

    terminal = (
        ordered
        .groupby(
            key_columns,
            dropna=False,
            as_index=False,
        )
        .tail(1)
        .copy()
    )

    return terminal


def calculate_summary(
    pitches: pd.DataFrame,
) -> dict[str, Any]:
    pitch_count = len(pitches)

    game_count = (
        pitches["game_pk"].nunique()
        if "game_pk" in pitches.columns
        else 0
    )

    batter_count = (
        pitches["batter_id"].nunique()
        if "batter_id" in pitches.columns
        else 0
    )

    terminal_pa = get_terminal_plate_appearances(
        pitches
    )

    plate_appearance_count = len(
        terminal_pa
    )

    swing_count = int(
        pitches["is_swing"].sum()
    )

    whiff_count = int(
        pitches["is_whiff"].sum()
    )

    contact_count = int(
        pitches["is_contact"].sum()
    )

    strike_count = int(
        pitches["is_strike"].sum()
    )

    csw_count = int(
        pitches["is_csw"].sum()
    )

    valid_zone_mask = (
        pitches["is_in_zone"]
        | pitches["is_out_of_zone"]
    )

    valid_zone_count = int(
        valid_zone_mask.sum()
    )

    zone_count = int(
        pitches.loc[
            valid_zone_mask,
            "is_in_zone",
        ].sum()
    )

    out_of_zone_count = int(
        pitches.loc[
            valid_zone_mask,
            "is_out_of_zone",
        ].sum()
    )

    chase_count = int(
        pitches.loc[
            valid_zone_mask,
            "is_chase",
        ].sum()
    )

    batted_balls = get_valid_batted_balls(
        pitches
    )

    batted_ball_count = len(
        batted_balls
    )

    hard_hit_count = int(
        batted_balls["is_hard_hit"].sum()
    )

    sweet_spot_count = int(
        batted_balls["is_sweet_spot"].sum()
    )

    release_velocity = numeric_column(
        pitches,
        "release_velocity",
    )

    release_spin_rate = numeric_column(
        pitches,
        "release_spin_rate",
    )

    release_extension = numeric_column(
        pitches,
        "release_extension",
    )

    batted_ball_exit_velocity = numeric_column(
        batted_balls,
        "launch_speed",
    )

    xwoba_values = numeric_column(
        pitches,
        "estimated_woba_using_speedangle",
    )

    xslg_values = numeric_column(
        pitches,
        "estimated_slg_using_speedangle",
    )

    return {
        "pitch_count": pitch_count,
        "game_count": game_count,
        "batter_count": batter_count,
        "plate_appearances": plate_appearance_count,

        "strike_rate": percentage(
            strike_count,
            pitch_count,
        ),

        "swing_rate": percentage(
            swing_count,
            pitch_count,
        ),

        "whiff_rate": percentage(
            whiff_count,
            swing_count,
        ),

        "csw_rate": percentage(
            csw_count,
            pitch_count,
        ),

        "zone_rate": percentage(
            zone_count,
            valid_zone_count,
        ),

        "chase_rate": percentage(
            chase_count,
            out_of_zone_count,
        ),

        "contact_rate": percentage(
            contact_count,
            swing_count,
        ),

        "average_velocity": round_or_none(
            release_velocity.mean(),
            1,
        ),

        "average_spin_rate": round_or_none(
            release_spin_rate.mean(),
            0,
        ),

        "average_extension": round_or_none(
            release_extension.mean(),
            1,
        ),

        "average_exit_velocity": round_or_none(
            batted_ball_exit_velocity.mean(),
            1,
        ),

        "hard_hit_rate": percentage(
            hard_hit_count,
            batted_ball_count,
        ),

        "sweet_spot_rate": percentage(
            sweet_spot_count,
            batted_ball_count,
        ),

        "xwoba": round_or_none(
            xwoba_values.dropna().mean(),
            3,
        ),

        "xslg": round_or_none(
            xslg_values.dropna().mean(),
            3,
        ),
    }

def calculate_pitch_arsenal(
    pitches: pd.DataFrame,
) -> list[dict[str, Any]]:
    total_pitch_count = len(pitches)

    records: list[dict[str, Any]] = []

    for pitch_type, group in pitches.groupby(
        "pitch_type",
        dropna=True,
    ):
        pitch_count = len(group)

        swing_count = int(
            group["is_swing"].sum()
        )

        whiff_count = int(
            group["is_whiff"].sum()
        )

        strike_count = int(
            group["is_strike"].sum()
        )

        csw_count = int(
            group["is_csw"].sum()
        )

        valid_zone_count = int(
            (
                group["is_in_zone"]
                | group["is_out_of_zone"]
            ).sum()
        )

        zone_count = int(
            group["is_in_zone"].sum()
        )

        out_of_zone_count = int(
            group["is_out_of_zone"].sum()
        )

        chase_count = int(
            group["is_chase"].sum()
        )

        batted_ball_count = int(
            group["is_batted_ball"].sum()
        )

        hard_hit_count = int(
            group["is_hard_hit"].sum()
        )

        record = {
            "pitch_type": str(pitch_type),

            "pitch_name": PITCH_NAMES.get(
                str(pitch_type),
                str(pitch_type),
            ),

            "pitch_count": pitch_count,

            "usage_percentage": percentage(
                pitch_count,
                total_pitch_count,
            ),

            "average_velocity": round_or_none(
                numeric_column(
                    group,
                    "release_velocity",
                ).mean(),
                1,
            ),

            "average_spin_rate": round_or_none(
                numeric_column(
                    group,
                    "release_spin_rate",
                ).mean(),
                0,
            ),

            "average_extension": round_or_none(
                numeric_column(
                    group,
                    "release_extension",
                ).mean(),
                1,
            ),

            "strike_percentage": percentage(
                strike_count,
                pitch_count,
            ),

            "zone_percentage": percentage(
                zone_count,
                valid_zone_count,
            ),

            "swing_percentage": percentage(
                swing_count,
                pitch_count,
            ),

            "whiff_percentage": percentage(
                whiff_count,
                swing_count,
            ),

            "csw_percentage": percentage(
                csw_count,
                pitch_count,
            ),

            "chase_percentage": percentage(
                chase_count,
                out_of_zone_count,
            ),

            "hard_hit_percentage": percentage(
                hard_hit_count,
                batted_ball_count,
            ),

            "average_exit_velocity": round_or_none(
                numeric_column(
                    group,
                    "launch_speed",
                )[
                    group["is_batted_ball"]
                ].mean(),
                1,
            ),

            "xwoba": round_or_none(
                numeric_column(
                    group,
                    "estimated_woba_using_speedangle",
                ).mean(),
                3,
            ),
        }

        records.append(record)

    records.sort(
        key=lambda record: (
            record.get(
                "usage_percentage"
            )
            or 0
        ),
        reverse=True,
    )

    return records

def calculate_movement_and_locations(
    pitches: pd.DataFrame,
    arsenal_table: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    movement_pitches = calculate_pitch_movement(
        pitches=pitches,
    )

    movement_summary = summarize_pitch_movement(
        movement_pitches=movement_pitches,
        minimum_pitch_count=5,
    )

    movement_records = movement_summary_to_records(
        movement_summary
    )

    updated_arsenal = add_movement_to_arsenal_table(
        arsenal_table=arsenal_table,
        movement_summary=movement_summary,
    )

    prepared_locations = prepare_location_data(
        pitches
    )

    location_columns = [
        "pitch_type",
        "plate_crossing_x",
        "plate_crossing_z",
    ]

    for optional_column in [
        "sz_top",
        "sz_bottom",
    ]:
        if optional_column in prepared_locations.columns:
            location_columns.append(
                optional_column
            )

    location_records = (
        prepared_locations
        .loc[:, location_columns]
        .replace(
            {
                np.nan: None,
                np.inf: None,
                -np.inf: None,
            }
        )
        .to_dict(
            orient="records"
        )
    )

    return (
        updated_arsenal,
        movement_records,
        location_records,
    )

def calculate_one_split(
    pitches: pd.DataFrame,
) -> dict[str, Any]:
    if pitches.empty:
        return {
            "plate_appearances": 0,
            "whiff_rate": None,
            "strikeout_rate": None,
            "walk_rate": None,
            "xwoba": None,
            "hard_hit_rate": None,
        }

    terminal_pa = get_terminal_plate_appearances(
        pitches
    )

    plate_appearances = len(
        terminal_pa
    )

    swing_count = int(
        pitches["is_swing"].sum()
    )

    whiff_count = int(
        pitches["is_whiff"].sum()
    )

    strikeout_count = int(
        terminal_pa["is_strikeout_event"].sum()
    )

    walk_count = int(
        terminal_pa["is_walk_event"].sum()
    )

    batted_balls = get_valid_batted_balls(
        pitches
    )

    batted_ball_count = len(
        batted_balls
    )

    hard_hit_count = int(
        batted_balls["is_hard_hit"].sum()
    )

    xwoba_values = numeric_column(
        pitches,
        "estimated_woba_using_speedangle",
    ).dropna()

    return {
        "plate_appearances": plate_appearances,

        "whiff_rate": percentage(
            whiff_count,
            swing_count,
        ),

        "strikeout_rate": percentage(
            strikeout_count,
            plate_appearances,
        ),

        "walk_rate": percentage(
            walk_count,
            plate_appearances,
        ),

        "xwoba": round_or_none(
            xwoba_values.mean(),
            3,
        ),

        "hard_hit_rate": percentage(
            hard_hit_count,
            batted_ball_count,
        ),
    }

def calculate_handedness_splits(
    pitches: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    if "stand" not in pitches.columns:
        return {
            "vs_lhb": calculate_one_split(
                pitches.iloc[0:0]
            ),
            "vs_rhb": calculate_one_split(
                pitches.iloc[0:0]
            ),
        }

    stand = (
        pitches["stand"]
        .fillna("")
        .astype(str)
        .str.upper()
    )

    left_handed = pitches[
        stand == "L"
    ].copy()

    right_handed = pitches[
        stand == "R"
    ].copy()

    return {
        "vs_lhb": calculate_one_split(
            left_handed
        ),
        "vs_rhb": calculate_one_split(
            right_handed
        ),
    }

def scale_metric_to_grade(
    value: Any,
    poor_value: float,
    average_value: float,
    elite_value: float,
    higher_is_better: bool = True,
) -> int:
    number = safe_float(value)

    if number is None:
        return 50

    if not higher_is_better:
        number = -number
        poor_value = -poor_value
        average_value = -average_value
        elite_value = -elite_value

    if number <= poor_value:
        grade = 30

    elif number < average_value:
        fraction = (
            number - poor_value
        ) / (
            average_value - poor_value
        )

        grade = 30 + fraction * 20

    elif number < elite_value:
        fraction = (
            number - average_value
        ) / (
            elite_value - average_value
        )

        grade = 50 + fraction * 20

    else:
        grade = 70

    rounded_grade = int(
        round(grade / 5.0) * 5
    )

    return max(
        20,
        min(
            80,
            rounded_grade,
        ),
    )


def calculate_grades(
    summary: dict[str, Any],
    arsenal_table: list[dict[str, Any]],
) -> dict[str, int]:
    average_velocity = summary.get(
        "average_velocity"
    )

    whiff_rate = summary.get(
        "whiff_rate"
    )

    chase_rate = summary.get(
        "chase_rate"
    )

    strike_rate = summary.get(
        "strike_rate"
    )

    zone_rate = summary.get(
        "zone_rate"
    )

    hard_hit_rate = summary.get(
        "hard_hit_rate"
    )

    average_exit_velocity = summary.get(
        "average_exit_velocity"
    )

    active_pitch_count = sum(
        1
        for pitch in arsenal_table
        if (
            safe_float(
                pitch.get(
                    "usage_percentage"
                ),
                0,
            )
            or 0
        ) >= 5.0
    )

    velocity_grade = scale_metric_to_grade(
        average_velocity,
        poor_value=89.0,
        average_value=92.5,
        elite_value=97.0,
    )

    whiff_grade = scale_metric_to_grade(
        whiff_rate,
        poor_value=18.0,
        average_value=24.0,
        elite_value=32.0,
    )

    chase_grade = scale_metric_to_grade(
        chase_rate,
        poor_value=24.0,
        average_value=30.0,
        elite_value=38.0,
    )

    strike_grade = scale_metric_to_grade(
        strike_rate,
        poor_value=59.0,
        average_value=64.0,
        elite_value=69.0,
    )

    zone_grade = scale_metric_to_grade(
        zone_rate,
        poor_value=35.0,
        average_value=42.0,
        elite_value=50.0,
    )

    hard_hit_grade = scale_metric_to_grade(
        hard_hit_rate,
        poor_value=45.0,
        average_value=38.0,
        elite_value=28.0,
        higher_is_better=False,
    )

    exit_velocity_grade = scale_metric_to_grade(
        average_exit_velocity,
        poor_value=91.0,
        average_value=88.0,
        elite_value=84.0,
        higher_is_better=False,
    )

    arsenal_grade = max(
        30,
        min(
            75,
            35 + active_pitch_count * 7,
        ),
    )

    stuff = int(
        round(
            (
                velocity_grade * 0.45
                + whiff_grade * 0.35
                + chase_grade * 0.20
            )
            / 5.0
        )
        * 5
    )

    command = int(
        round(
            (
                strike_grade * 0.60
                + zone_grade * 0.40
            )
            / 5.0
        )
        * 5
    )

    bat_missing = int(
        round(
            (
                whiff_grade * 0.65
                + chase_grade * 0.35
            )
            / 5.0
        )
        * 5
    )

    contact_management = int(
        round(
            (
                hard_hit_grade * 0.60
                + exit_velocity_grade * 0.40
            )
            / 5.0
        )
        * 5
    )

    overall = int(
        round(
            (
                stuff * 0.25
                + command * 0.20
                + bat_missing * 0.20
                + contact_management * 0.15
                + arsenal_grade * 0.20
            )
            / 5.0
        )
        * 5
    )

    return {
        "stuff": max(
            20,
            min(
                80,
                stuff,
            ),
        ),

        "command": max(
            20,
            min(
                80,
                command,
            ),
        ),

        "bat_missing": max(
            20,
            min(
                80,
                bat_missing,
            ),
        ),

        "contact_management": max(
            20,
            min(
                80,
                contact_management,
            ),
        ),

        "arsenal": max(
            20,
            min(
                80,
                int(
                    round(
                        arsenal_grade / 5.0
                    )
                    * 5
                ),
            ),
        ),

        "overall": max(
            20,
            min(
                80,
                overall,
            ),
        ),
    }

def best_pitch_by_metric(
    arsenal_table: list[dict[str, Any]],
    metric: str,
    minimum_pitch_count: int = 20,
) -> dict[str, Any] | None:
    candidates = [
        pitch
        for pitch in arsenal_table
        if (
            safe_int(
                pitch.get(
                    "pitch_count"
                )
            )
            >= minimum_pitch_count
            and safe_float(
                pitch.get(metric)
            )
            is not None
        )
    ]

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda pitch: (
            safe_float(
                pitch.get(metric),
                -999,
            )
            or -999
        ),
    )


def build_strengths(
    summary: dict[str, Any],
    arsenal_table: list[dict[str, Any]],
) -> list[str]:
    strengths: list[str] = []

    average_velocity = safe_float(
        summary.get(
            "average_velocity"
        )
    )

    chase_rate = safe_float(
        summary.get(
            "chase_rate"
        )
    )

    hard_hit_rate = safe_float(
        summary.get(
            "hard_hit_rate"
        )
    )

    whiff_rate = safe_float(
        summary.get(
            "whiff_rate"
        )
    )

    if average_velocity is not None:
        if average_velocity >= 95:
            strengths.append(
                f"Premium overall velocity profile, "
                f"averaging {average_velocity:.1f} mph."
            )

        elif average_velocity >= 92:
            strengths.append(
                f"Above-average overall pitch velocity "
                f"at {average_velocity:.1f} mph."
            )

    if chase_rate is not None and chase_rate >= 34:
        strengths.append(
            f"Generates frequent swings outside the "
            f"strike zone with a {chase_rate:.1f}% "
            f"chase rate."
        )

    if whiff_rate is not None and whiff_rate >= 25:
        strengths.append(
            f"Produces a strong overall swing-and-miss "
            f"profile with a {whiff_rate:.1f}% whiff rate."
        )

    if hard_hit_rate is not None and hard_hit_rate <= 32:
        strengths.append(
            f"Limits hard contact effectively at "
            f"{hard_hit_rate:.1f}%."
        )

    active_pitch_count = sum(
        1
        for pitch in arsenal_table
        if (
            safe_float(
                pitch.get(
                    "usage_percentage"
                ),
                0,
            )
            or 0
        ) >= 5
    )

    if active_pitch_count >= 5:
        strengths.append(
            f"Uses a deep {active_pitch_count}-pitch mix, "
            f"providing multiple velocity and movement bands."
        )

    best_whiff_pitch = best_pitch_by_metric(
        arsenal_table,
        "whiff_percentage",
    )

    if best_whiff_pitch:
        whiff = safe_float(
            best_whiff_pitch.get(
                "whiff_percentage"
            )
        )

        if whiff is not None and whiff >= 30:
            strengths.append(
                f"The {best_whiff_pitch.get('pitch_name')} "
                f"is the leading bat-missing pitch with a "
                f"{whiff:.1f}% whiff rate."
            )

    if not strengths:
        strengths.append(
            "Provides a balanced mix of strikes, chase, "
            "and contact management."
        )

    return strengths[:4]


def build_concerns(
    summary: dict[str, Any],
    arsenal_table: list[dict[str, Any]],
) -> list[str]:
    concerns: list[str] = []

    strike_rate = safe_float(
        summary.get(
            "strike_rate"
        )
    )

    zone_rate = safe_float(
        summary.get(
            "zone_rate"
        )
    )

    whiff_rate = safe_float(
        summary.get(
            "whiff_rate"
        )
    )

    chase_rate = safe_float(
        summary.get(
            "chase_rate"
        )
    )

    if strike_rate is not None and strike_rate < 62:
        concerns.append(
            f"Overall strike rate is below the preferred "
            f"range at {strike_rate:.1f}%."
        )

    if zone_rate is not None and zone_rate < 40:
        concerns.append(
            f"Below-average zone rate of {zone_rate:.1f}% "
            f"can create command-related risk."
        )

    if (
        chase_rate is not None
        and chase_rate >= 35
        and zone_rate is not None
        and zone_rate < 42
    ):
        concerns.append(
            "The profile depends heavily on hitters "
            "expanding outside the strike zone."
        )

    if whiff_rate is not None and whiff_rate < 22:
        concerns.append(
            f"Overall swing-and-miss production is limited "
            f"at a {whiff_rate:.1f}% whiff rate."
        )

    for pitch in arsenal_table:
        usage = safe_float(
            pitch.get(
                "usage_percentage"
            ),
            0,
        ) or 0

        whiff = safe_float(
            pitch.get(
                "whiff_percentage"
            )
        )

        if (
            usage >= 10
            and whiff is not None
            and whiff < 15
        ):
            concerns.append(
                f"The {pitch.get('pitch_name')} produces "
                f"limited swing-and-miss at {whiff:.1f}%."
            )

            break

    if not concerns:
        concerns.append(
            "No major statistical weakness is evident, "
            "though command consistency should continue "
            "to be monitored."
        )

    return concerns[:4]


def build_scouting_summary(
    pitcher_name: str,
    summary: dict[str, Any],
    arsenal_table: list[dict[str, Any]],
    grades: dict[str, int],
) -> str:
    overall_grade = grades.get(
        "overall",
        50,
    )

    average_velocity = safe_float(
        summary.get("average_velocity")
    )

    zone_rate = safe_float(
        summary.get("zone_rate")
    )

    chase_rate = safe_float(
        summary.get("chase_rate")
    )

    hard_hit_rate = safe_float(
        summary.get("hard_hit_rate")
    )

    active_pitches = [
        pitch
        for pitch in arsenal_table
        if (
            safe_float(
                pitch.get("usage_percentage"),
                0,
            )
            or 0
        ) >= 5.0
    ]

    best_whiff_pitch = best_pitch_by_metric(
        arsenal_table,
        "whiff_percentage",
    )

    if overall_grade >= 65:
        role_description = (
            "a high-end frontline starter"
        )

    elif overall_grade >= 55:
        role_description = (
            "an above-average major-league starter"
        )

    elif overall_grade >= 45:
        role_description = (
            "a solid major-league starter"
        )

    else:
        role_description = (
            "a developing major-league pitcher"
        )

    sentence_one = (
        f"{pitcher_name} profiles as {role_description} "
        f"with a deep {len(active_pitches)}-pitch arsenal."
    )

    profile_parts: list[str] = []

    if average_velocity is not None:
        profile_parts.append(
            f"{average_velocity:.1f} mph average velocity"
        )

    if zone_rate is not None:
        profile_parts.append(
            f"a {zone_rate:.1f}% zone rate"
        )

    if chase_rate is not None:
        profile_parts.append(
            f"a {chase_rate:.1f}% chase rate"
        )

    if hard_hit_rate is not None:
        profile_parts.append(
            f"a {hard_hit_rate:.1f}% hard-hit rate"
        )

    if profile_parts:
        sentence_two = (
            "The overall profile includes "
            + ", ".join(profile_parts)
            + "."
        )

    else:
        sentence_two = (
            "The arsenal provides multiple velocity "
            "and movement shapes."
        )

    if best_whiff_pitch:
        pitch_name = best_whiff_pitch.get(
            "pitch_name",
            "top secondary pitch",
        )

        pitch_whiff = safe_float(
            best_whiff_pitch.get(
                "whiff_percentage"
            )
        )

        if pitch_whiff is not None:
            sentence_three = (
                f"The {pitch_name} is the strongest "
                f"bat-missing pitch, producing a "
                f"{pitch_whiff:.1f}% whiff rate."
            )

        else:
            sentence_three = (
                f"The {pitch_name} currently grades as "
                f"the strongest bat-missing offering."
            )

    else:
        sentence_three = (
            "The pitch mix provides several usable "
            "swing-and-miss options."
        )

    sentence_four = (
        "Command remains the primary area to monitor, "
        "but the quality and depth of the arsenal support "
        "continued starter value."
    )

    return " ".join(
        [
            sentence_one,
            sentence_two,
            sentence_three,
            sentence_four,
        ]
    )

def build_pitcher_report(
    pitches: pd.DataFrame,
    pitcher_id: int,
    season: int,
    pitcher_name_override: str | None = None,
    team_name_override: str | None = None,
    throws_override: str | None = None,
) -> dict[str, Any]:
    flagged_pitches = add_pitch_flags(
        pitches
    )

    metadata = load_pitcher_metadata(
        pitcher_id
    )

    if pitcher_name_override:
        metadata["pitcher_name"] = (
            pitcher_name_override
        )

    if team_name_override:
        metadata["team_name"] = (
            team_name_override
        )

    if throws_override:
        metadata["throws"] = (
            throws_override
        )

    summary = calculate_summary(
        flagged_pitches
    )

    arsenal_table = calculate_pitch_arsenal(
        flagged_pitches
    )

    (
        arsenal_table,
        movement_chart,
        pitch_locations,
    ) = calculate_movement_and_locations(
        pitches=flagged_pitches,
        arsenal_table=arsenal_table,
    )

    grades = calculate_grades(
        summary=summary,
        arsenal_table=arsenal_table,
    )

    splits = calculate_handedness_splits(
        flagged_pitches
    )

    strengths = build_strengths(
        summary=summary,
        arsenal_table=arsenal_table,
    )

    concerns = build_concerns(
        summary=summary,
        arsenal_table=arsenal_table,
    )

    scouting_summary = build_scouting_summary(
        pitcher_name=metadata[
            "pitcher_name"
        ],
        summary=summary,
        arsenal_table=arsenal_table,
        grades=grades,
    )

    report = {
        "pitcher_id": pitcher_id,
        "pitcher_name": metadata[
            "pitcher_name"
        ],
        "team_name": metadata[
            "team_name"
        ],
        "throws": metadata[
            "throws"
        ],
        "season": season,

        "grades": grades,
        "summary": summary,
        "arsenal_table": arsenal_table,
        "movement_chart": movement_chart,
        "pitch_locations": pitch_locations,
        "splits": splits,
        "strengths": strengths,
        "concerns": concerns,
        "scouting_summary": scouting_summary,
    }

    return clean_json_value(
        report
    )

def save_report_json(
    report: dict[str, Any],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            clean_json_value(
                report
            ),
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path



def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a complete pitcher scouting report "
            "from PostgreSQL Statcast data."
        )
    )

    parser.add_argument(
        "--pitcher-id",
        type=int,
        required=True,
        help="MLB pitcher ID.",
    )

    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Season year.",
    )

    parser.add_argument(
        "--format",
        choices=[
            "png",
            "pdf",
            "json",
            "all",
        ],
        default="all",
        help="Report output format.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory for generated reports.",
    )

    parser.add_argument(
        "--pitcher-name",
        type=str,
        default=None,
        help=(
            "Optional pitcher-name override. "
            "Example: --pitcher-name 'Paul Skenes'"
        ),
    )

    parser.add_argument(
        "--team-name",
        type=str,
        default=None,
        help=(
            "Optional team-name override. "
            "Example: --team-name 'Pittsburgh Pirates'"
        ),
    )

    parser.add_argument(
        "--throws",
        type=str,
        default=None,
        help=(
            "Optional throwing-hand override. "
            "Example: --throws RHP"
        ),
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the report after generating it.",
    )

    return parser.parse_args()

def main() -> None:
    arguments = parse_arguments()

    output_directory = arguments.output_dir

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    base_filename = (
        f"pitcher_report_"
        f"{arguments.pitcher_id}_"
        f"{arguments.season}"
    )

    png_path = output_directory / (
        base_filename + ".png"
    )

    pdf_path = output_directory / (
        base_filename + ".pdf"
    )

    json_path = output_directory / (
        base_filename + ".json"
    )

    pitches = load_pitcher_pitches(
        pitcher_id=arguments.pitcher_id,
        season=arguments.season,
    )

    report = build_pitcher_report(
        pitches=pitches,
        pitcher_id=arguments.pitcher_id,
        season=arguments.season,
        pitcher_name_override=(
            arguments.pitcher_name
        ),
        team_name_override=(
            arguments.team_name
        ),
        throws_override=(
            arguments.throws
        ),
    )

    print("\nReport summary")
    print("-" * 60)
    print(
        f"Pitcher: "
        f"{report.get('pitcher_name')}"
    )
    print(
        f"Games: "
        f"{report.get('summary', {}).get('game_count')}"
    )
    print(
        f"Pitches: "
        f"{report.get('summary', {}).get('pitch_count')}"
    )
    print(
        f"Arsenal rows: "
        f"{len(report.get('arsenal_table', []))}"
    )
    print(
        f"Movement rows: "
        f"{len(report.get('movement_chart', []))}"
    )
    print(
        f"Location rows: "
        f"{len(report.get('pitch_locations', []))}"
    )
    print("-" * 60)

    # PNG export creates the single-page overview preview.
    if arguments.format in {
        "png",
        "all",
    }:
        final_png_path = create_pitcher_report_card(
            report=report,
            output_path=png_path,
            show=arguments.show,
        )

        print(
            f"Created PNG preview: {final_png_path}"
        )

    # PDF export must be sent directly to create_pitcher_report_card.
    # That function detects the .pdf suffix and writes all report pages
    # through matplotlib.backends.backend_pdf.PdfPages.
    if arguments.format in {
        "pdf",
        "all",
    }:
        final_pdf_path = create_pitcher_report_card(
            report=report,
            output_path=pdf_path,
            show=arguments.show,
        )

        print(
            f"Created multi-page PDF: {final_pdf_path}"
        )

    if arguments.format in {
        "json",
        "all",
    }:
        final_json_path = save_report_json(
            report=report,
            output_path=json_path,
        )

        print(
            f"Created JSON: {final_json_path}"
        )

    print("\nPitcher report generation complete.")


if __name__ == "__main__":
    main()