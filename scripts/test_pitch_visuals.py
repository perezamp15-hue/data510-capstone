from pathlib import Path

import pandas as pd
from sqlalchemy import text

from db_client import get_engine
from visualizations.pitch_location_movement import (
    create_pitch_location_movement_figure,
)


PITCHER_ID = 694973
SEASON = 2026


QUERY = """
SELECT
    sp.pitch_id,
    sp.game_pk,
    sp.game_date,
    sp.pitch_type,
    sp.release_velocity,
    sp.release_spin_rate,
    sp.release_extension,

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

    sp.batter_id,
    sp.pitcher_id
FROM public.statcast_pitches AS sp
WHERE sp.pitcher_id = :pitcher_id
  AND EXTRACT(YEAR FROM sp.game_date) = :season
  AND sp.pitch_type IS NOT NULL
ORDER BY
    sp.game_date,
    sp.game_pk,
    sp.at_bat_number,
    sp.pitch_number
"""


def main() -> None:
    engine = get_engine()

    with engine.connect() as connection:
        pitches = pd.read_sql(
            text(QUERY),
            connection,
            params={
                "pitcher_id": PITCHER_ID,
                "season": SEASON,
            },
        )

    print(f"Loaded {len(pitches):,} pitches")

    result = create_pitch_location_movement_figure(
        pitches=pitches,
        output_path=Path(
            "output/pitch_location_movement_694973_2026.png"
        ),
        pitcher_name="Paul Skenes",
        season=SEASON,
        top_n_locations=3,
    )

    movement_summary = result["movement_summary"]

    print("\nEstimated movement summary:")
    print(
        movement_summary[
            [
                "pitch_type",
                "pitch_count",
                "usage_percentage",
                "horizontal_break",
                "vertical_break",
            ]
        ].to_string(index=False)
    )

    print(
        "\nCreated:",
        result["output_path"],
    )


if __name__ == "__main__":
    main()