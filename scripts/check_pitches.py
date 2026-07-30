"""Verify collected pitch data."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import Game, Pitch


def main() -> int:
    with session_scope() as session:
        pitch_count = session.scalar(
            select(func.count()).select_from(Pitch)
        ) or 0

        game_count = session.scalar(
            select(func.count(func.distinct(Pitch.game_pk)))
        ) or 0

        duplicate_keys = session.execute(
            select(
                Pitch.game_pk,
                Pitch.at_bat_number,
                Pitch.pitch_number,
                func.count().label("row_count"),
            )
            .group_by(
                Pitch.game_pk,
                Pitch.at_bat_number,
                Pitch.pitch_number,
            )
            .having(func.count() > 1)
        ).all()

        missing_pitchers = session.scalar(
            select(func.count())
            .select_from(Pitch)
            .where(Pitch.pitcher_id.is_(None))
        ) or 0

        missing_batters = session.scalar(
            select(func.count())
            .select_from(Pitch)
            .where(Pitch.batter_id.is_(None))
        ) or 0

        game_summaries = session.execute(
            select(
                Game.game_pk,
                Game.game_date,
                Game.detailed_status,
                Game.pitches_collected,
                Game.pitch_count,
                Game.pitch_collection_error,
            )
            .where(Game.pitches_collected.is_(True))
            .order_by(Game.game_date.desc())
            .limit(20)
        ).all()

    print(f"Stored pitches: {pitch_count}")
    print(f"Games represented: {game_count}")
    print(f"Duplicate pitch keys: {len(duplicate_keys)}")
    print(f"Pitches without pitcher: {missing_pitchers}")
    print(f"Pitches without batter: {missing_batters}")

    print()
    print("Recently collected games:")

    for game in game_summaries:
        print(
            f"{game.game_pk} | "
            f"{game.game_date} | "
            f"{game.detailed_status or 'Unknown':<15} | "
            f"pitches={game.pitch_count}"
        )

    if pitch_count == 0:
        print("\nVerification failed: no pitches stored.")
        return 1

    if duplicate_keys:
        print("\nVerification failed: duplicate pitches found.")
        return 1

    if missing_pitchers or missing_batters:
        print(
            "\nVerification failed: player IDs are missing."
        )
        return 1

    print("\nPitch verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())