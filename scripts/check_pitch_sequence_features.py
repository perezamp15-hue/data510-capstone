"""Verify pitch-sequence training features."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import PitchSequenceFeature


def main() -> int:
    """Check feature counts, duplicates, and values."""
    with session_scope() as session:
        row_count = session.scalar(
            select(func.count())
            .select_from(PitchSequenceFeature)
        ) or 0

        duplicate_keys = session.execute(
            select(
                PitchSequenceFeature.game_pk,
                PitchSequenceFeature.at_bat_number,
                PitchSequenceFeature.pitch_number,
                func.count().label("row_count"),
            )
            .group_by(
                PitchSequenceFeature.game_pk,
                PitchSequenceFeature.at_bat_number,
                PitchSequenceFeature.pitch_number,
            )
            .having(func.count() > 1)
        ).all()

        invalid_counts = session.scalar(
            select(func.count())
            .select_from(PitchSequenceFeature)
            .where(
                (PitchSequenceFeature.balls_before_pitch < 0)
                | (PitchSequenceFeature.balls_before_pitch > 3)
                | (PitchSequenceFeature.strikes_before_pitch < 0)
                | (PitchSequenceFeature.strikes_before_pitch > 2)
            )
        ) or 0

        missing_targets = session.scalar(
            select(func.count())
            .select_from(PitchSequenceFeature)
            .where(
                PitchSequenceFeature.target_pitch_type.is_(None)
            )
        ) or 0

        zone_counts = session.execute(
            select(
                PitchSequenceFeature.target_pitch_zone,
                func.count().label("row_count"),
            )
            .group_by(
                PitchSequenceFeature.target_pitch_zone
            )
            .order_by(
                func.count().desc()
            )
        ).all()

        sample_rows = session.execute(
            select(
                PitchSequenceFeature.game_pk,
                PitchSequenceFeature.at_bat_number,
                PitchSequenceFeature.pitch_number,
                PitchSequenceFeature.balls_before_pitch,
                PitchSequenceFeature.strikes_before_pitch,
                PitchSequenceFeature.previous_pitch_type,
                PitchSequenceFeature.previous_pitch_zone,
                PitchSequenceFeature.target_pitch_type,
                PitchSequenceFeature.target_pitch_zone,
            )
            .order_by(
                PitchSequenceFeature.game_date.desc(),
                PitchSequenceFeature.game_pk,
                PitchSequenceFeature.at_bat_number,
                PitchSequenceFeature.pitch_number,
            )
            .limit(20)
        ).all()

    print(f"Feature rows: {row_count}")
    print(f"Duplicate sequence keys: {len(duplicate_keys)}")
    print(f"Invalid count states: {invalid_counts}")
    print(f"Missing pitch-type targets: {missing_targets}")

    print()
    print("Target zone distribution:")

    for zone, count in zone_counts:
        print(f"  {zone or 'missing':<15} {count:>8}")

    print()
    print("Sample sequence rows:")

    for row in sample_rows:
        print(
            f"game={row.game_pk} "
            f"pa={row.at_bat_number} "
            f"pitch={row.pitch_number} "
            f"count={row.balls_before_pitch}-"
            f"{row.strikes_before_pitch} "
            f"previous={row.previous_pitch_type or '-'} "
            f"previous_zone={row.previous_pitch_zone or '-'} "
            f"target={row.target_pitch_type} "
            f"target_zone={row.target_pitch_zone or '-'}"
        )

    if row_count == 0:
        print("\nFailure: no sequence features exist.")
        return 1

    if duplicate_keys:
        print("\nFailure: duplicate sequence rows exist.")
        return 1

    if invalid_counts:
        print("\nFailure: invalid count states exist.")
        return 1

    if missing_targets:
        print("\nFailure: target pitch types are missing.")
        return 1

    print("\nPitch sequence feature verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())