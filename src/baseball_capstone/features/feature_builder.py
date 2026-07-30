"""Central feature-engineering orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import Game, Pitch, Player
from baseball_capstone.features.batter_features import (
    add_batter_features,
)
from baseball_capstone.features.count_features import (
    add_count_features,
)
from baseball_capstone.features.environmental_features import (
    add_environmental_features,
)
from baseball_capstone.features.fatigue_features import (
    add_fatigue_features,
)
from baseball_capstone.features.game_state_features import (
    add_game_state_features,
)
from baseball_capstone.features.matchup_features import (
    add_matchup_features,
)
from baseball_capstone.features.pitcher_features import (
    add_pitcher_features,
)
from baseball_capstone.features.sequence_features import (
    add_sequence_features,
)
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FeatureBuildConfig:
    """Settings for a feature-build run."""

    start_date: date
    end_date: date
    pitcher_window: int = 100
    batter_window: int = 100
    matchup_window: int = 50


@dataclass(frozen=True, slots=True)
class FeatureBuildResult:
    """Summary of a feature-build run."""

    row_count: int
    column_count: int
    output_path: Path | None


def load_pitch_data(config: FeatureBuildConfig) -> pd.DataFrame:
    """Load raw pitch rows and contextual dimensions."""
    with session_scope() as session:
        rows = session.execute(
            select(
                Pitch.game_pk,
                Pitch.game_date,
                Pitch.at_bat_number,
                Pitch.pitch_number,
                Pitch.inning,
                Pitch.inning_half,
                Pitch.outs,
                Pitch.balls,
                Pitch.strikes,
                Pitch.pitcher_id,
                Pitch.batter_id,
                Pitch.pitch_type,
                Pitch.pitch_name,
                Pitch.description,
                Pitch.release_speed,
                Pitch.release_spin_rate,
                Pitch.release_extension,
                Pitch.plate_x,
                Pitch.plate_z,
                Pitch.zone,
                Pitch.is_ball,
                Pitch.is_strike,
                Pitch.is_in_play,
                Pitch.launch_speed,
                Pitch.launch_angle,
                Pitch.runner_on_first,
                Pitch.runner_on_second,
                Pitch.runner_on_third,
                Pitch.home_score,
                Pitch.away_score,
                Game.park_id,
                Game.temperature_f,
                Game.wind_speed_mph,
                Game.wind_direction,
                Game.weather_condition,
                Game.day_night,
                Player.throws.label("pitcher_hand"),
            )
            .join(Game, Game.game_pk == Pitch.game_pk)
            .join(
                Player,
                Player.player_id == Pitch.pitcher_id,
            )
            .where(Pitch.game_date.between(
                config.start_date,
                config.end_date,
            ))
            .order_by(
                Pitch.game_date,
                Pitch.game_pk,
                Pitch.at_bat_number,
                Pitch.pitch_number,
            )
        ).mappings().all()

    dataframe = pd.DataFrame(rows)

    if dataframe.empty:
        return dataframe

    with session_scope() as session:
        batter_rows = session.execute(
            select(
                Player.player_id,
                Player.bats,
            )
            .where(
                Player.player_id.in_(
                    dataframe["batter_id"].unique().tolist()
                )
            )
        ).all()

    batter_side_map = {
        player_id: bats
        for player_id, bats in batter_rows
    }

    dataframe["batter_side"] = dataframe[
        "batter_id"
    ].map(batter_side_map)

    return dataframe


def build_feature_dataframe(
    config: FeatureBuildConfig,
) -> pd.DataFrame:
    """Run all feature modules in dependency-safe order."""
    dataframe = load_pitch_data(config)
    # Convert PostgreSQL Decimal values to float
    for column in dataframe.columns:
        if dataframe[column].dtype == "object":
            dataframe[column] = dataframe[column].map(
                lambda value: float(value)
                if isinstance(value, Decimal)
                else value
            )
    if dataframe.empty:
        return dataframe

    dataframe = add_sequence_features(dataframe)
    dataframe = add_count_features(dataframe)
    dataframe = add_game_state_features(dataframe)
    dataframe = add_fatigue_features(dataframe)

    dataframe = add_pitcher_features(
        dataframe,
        rolling_window=config.pitcher_window,
    )

    dataframe = add_batter_features(
        dataframe,
        rolling_window=config.batter_window,
    )

    dataframe = add_matchup_features(
        dataframe,
        rolling_window=config.matchup_window,
    )

    dataframe = add_environmental_features(dataframe)

    dataframe["target_pitch_type"] = dataframe["pitch_type"]
    dataframe["target_plate_x"] = dataframe["plate_x"]
    dataframe["target_plate_z"] = dataframe["plate_z"]

    return dataframe


def build_and_export_features(
    config: FeatureBuildConfig,
    output_path: Path | None = None,
) -> FeatureBuildResult:
    """Build features and optionally export them as Parquet."""
    dataframe = build_feature_dataframe(config)

    if output_path is not None:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        dataframe.to_parquet(
            output_path,
            index=False,
        )

    return FeatureBuildResult(
        row_count=len(dataframe),
        column_count=len(dataframe.columns),
        output_path=output_path,
    )
