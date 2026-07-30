"""Build pitch-sequence model features from stored pitch data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text

from baseball_capstone.database.engine import session_scope


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeatureBuildResult:
    """Summary of one feature-table build."""

    start_date: date
    end_date: date
    source_pitches: int
    rows_deleted: int
    rows_inserted: int


COUNT_SOURCE_SQL = text(
    """
    SELECT COUNT(*)
    FROM pitches
    WHERE game_date BETWEEN :start_date AND :end_date
      AND is_pitch IS TRUE
      AND pitch_type IS NOT NULL
    """
)


DELETE_FEATURES_SQL = text(
    """
    DELETE FROM pitch_sequence_features
    WHERE game_date BETWEEN :start_date AND :end_date
    """
)


INSERT_FEATURES_SQL = text(
    """
    WITH pitch_base AS (
        SELECT
            p.game_pk,
            p.game_date,
            EXTRACT(YEAR FROM p.game_date)::INTEGER AS season,
            p.at_bat_number,
            p.pitch_number,
            p.pitcher_id,
            p.batter_id,

            pitcher.throws AS pitcher_hand,
            batter.bats AS batter_side,

            p.inning,
            p.inning_half,
            p.outs,
            p.balls,
            p.strikes,

            p.pitch_type,
            p.pitch_name,
            p.description,

            p.plate_x,
            p.plate_z,
            p.strike_zone_top,
            p.strike_zone_bottom,
            p.release_speed,

            p.is_ball,
            p.is_strike,
            p.is_in_play,

            COALESCE(p.runner_on_first, FALSE) AS runner_on_first,
            COALESCE(p.runner_on_second, FALSE) AS runner_on_second,
            COALESCE(p.runner_on_third, FALSE) AS runner_on_third,

            CASE
                WHEN p.plate_x IS NULL
                  OR p.plate_z IS NULL
                  OR p.strike_zone_top IS NULL
                  OR p.strike_zone_bottom IS NULL
                  OR p.strike_zone_top <= p.strike_zone_bottom
                THEN NULL

                WHEN p.plate_x < -0.95
                  OR p.plate_x > 0.95
                  OR p.plate_z < p.strike_zone_bottom
                  OR p.plate_z > p.strike_zone_top
                THEN 'chase'

                WHEN p.plate_z >= (
                    p.strike_zone_bottom
                    + (
                        p.strike_zone_top
                        - p.strike_zone_bottom
                    ) * 0.6666667
                )
                AND p.plate_x < -0.3166667
                THEN 'up-left'

                WHEN p.plate_z >= (
                    p.strike_zone_bottom
                    + (
                        p.strike_zone_top
                        - p.strike_zone_bottom
                    ) * 0.6666667
                )
                AND p.plate_x <= 0.3166667
                THEN 'up-middle'

                WHEN p.plate_z >= (
                    p.strike_zone_bottom
                    + (
                        p.strike_zone_top
                        - p.strike_zone_bottom
                    ) * 0.6666667
                )
                THEN 'up-right'

                WHEN p.plate_z >= (
                    p.strike_zone_bottom
                    + (
                        p.strike_zone_top
                        - p.strike_zone_bottom
                    ) * 0.3333333
                )
                AND p.plate_x < -0.3166667
                THEN 'middle-left'

                WHEN p.plate_z >= (
                    p.strike_zone_bottom
                    + (
                        p.strike_zone_top
                        - p.strike_zone_bottom
                    ) * 0.3333333
                )
                AND p.plate_x <= 0.3166667
                THEN 'heart'

                WHEN p.plate_z >= (
                    p.strike_zone_bottom
                    + (
                        p.strike_zone_top
                        - p.strike_zone_bottom
                    ) * 0.3333333
                )
                THEN 'middle-right'

                WHEN p.plate_x < -0.3166667
                THEN 'down-left'

                WHEN p.plate_x <= 0.3166667
                THEN 'down-middle'

                ELSE 'down-right'
            END AS target_pitch_zone

        FROM pitches AS p

        JOIN players AS pitcher
          ON pitcher.player_id = p.pitcher_id

        JOIN players AS batter
          ON batter.player_id = p.batter_id

        WHERE p.game_date BETWEEN :start_date AND :end_date
          AND p.is_pitch IS TRUE
          AND p.pitch_type IS NOT NULL
    ),

    sequenced AS (
        SELECT
            pitch_base.*,

            COALESCE(
                LAG(balls, 1) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ),
                0
            ) AS balls_before_pitch,

            COALESCE(
                LAG(strikes, 1) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ),
                0
            ) AS strikes_before_pitch,

            COALESCE(
                LAG(outs, 1) OVER (
                    PARTITION BY game_pk, at_bat_number
                    ORDER BY pitch_number
                ),
                outs,
                0
            ) AS outs_before_pitch,

            LAG(pitch_type, 1) OVER (
                PARTITION BY game_pk, at_bat_number
                ORDER BY pitch_number
            ) AS previous_pitch_type,

            LAG(target_pitch_zone, 1) OVER (
                PARTITION BY game_pk, at_bat_number
                ORDER BY pitch_number
            ) AS previous_pitch_zone,

            LAG(description, 1) OVER (
                PARTITION BY game_pk, at_bat_number
                ORDER BY pitch_number
            ) AS previous_pitch_result,

            LAG(pitch_type, 2) OVER (
                PARTITION BY game_pk, at_bat_number
                ORDER BY pitch_number
            ) AS second_previous_pitch_type,

            LAG(target_pitch_zone, 2) OVER (
                PARTITION BY game_pk, at_bat_number
                ORDER BY pitch_number
            ) AS second_previous_pitch_zone,

            LAG(pitch_type, 3) OVER (
                PARTITION BY game_pk, at_bat_number
                ORDER BY pitch_number
            ) AS third_previous_pitch_type

        FROM pitch_base
    )

    INSERT INTO pitch_sequence_features (
        game_pk,
        game_date,
        season,
        at_bat_number,
        pitch_number,
        pitcher_id,
        batter_id,
        pitcher_hand,
        batter_side,
        inning,
        inning_half,
        outs_before_pitch,
        balls_before_pitch,
        strikes_before_pitch,
        previous_pitch_type,
        previous_pitch_zone,
        previous_pitch_result,
        second_previous_pitch_type,
        second_previous_pitch_zone,
        third_previous_pitch_type,
        runner_on_first,
        runner_on_second,
        runner_on_third,
        target_pitch_type,
        target_pitch_name,
        target_pitch_zone,
        target_plate_x,
        target_plate_z,
        target_release_speed,
        target_description,
        target_is_ball,
        target_is_strike,
        target_is_in_play
    )

    SELECT
        game_pk,
        game_date,
        season,
        at_bat_number,
        pitch_number,
        pitcher_id,
        batter_id,
        pitcher_hand,
        batter_side,
        inning,
        inning_half,
        outs_before_pitch,
        balls_before_pitch,
        strikes_before_pitch,
        previous_pitch_type,
        previous_pitch_zone,
        previous_pitch_result,
        second_previous_pitch_type,
        second_previous_pitch_zone,
        third_previous_pitch_type,
        runner_on_first,
        runner_on_second,
        runner_on_third,
        pitch_type,
        pitch_name,
        target_pitch_zone,
        plate_x,
        plate_z,
        release_speed,
        description,
        is_ball,
        is_strike,
        is_in_play

    FROM sequenced
    """
)


COUNT_FEATURES_SQL = text(
    """
    SELECT COUNT(*)
    FROM pitch_sequence_features
    WHERE game_date BETWEEN :start_date AND :end_date
    """
)


def build_pitch_sequence_features(
    start_date: date,
    end_date: date,
) -> FeatureBuildResult:
    """Rebuild sequence features for an inclusive date range."""
    if end_date < start_date:
        raise ValueError(
            "end_date cannot be earlier than start_date."
        )

    parameters = {
        "start_date": start_date,
        "end_date": end_date,
    }

    with session_scope() as session:
        source_pitches = session.scalar(
            COUNT_SOURCE_SQL,
            parameters,
        ) or 0

        delete_result = session.execute(
            DELETE_FEATURES_SQL,
            parameters,
        )

        rows_deleted = max(delete_result.rowcount or 0, 0)

        if source_pitches:
            session.execute(
                INSERT_FEATURES_SQL,
                parameters,
            )

        rows_inserted = session.scalar(
            COUNT_FEATURES_SQL,
            parameters,
        ) or 0

    LOGGER.info(
        "Pitch-sequence features built: "
        "start=%s end=%s source=%s deleted=%s inserted=%s",
        start_date,
        end_date,
        source_pitches,
        rows_deleted,
        rows_inserted,
    )

    return FeatureBuildResult(
        start_date=start_date,
        end_date=end_date,
        source_pitches=source_pitches,
        rows_deleted=rows_deleted,
        rows_inserted=rows_inserted,
    )