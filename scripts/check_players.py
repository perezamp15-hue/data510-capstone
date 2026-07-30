"""Verify collected MLB players."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import (
    CollectionRun,
    Player,
    Team,
)


def main() -> int:
    """Validate player records and team assignments."""
    with session_scope() as session:
        player_count = session.scalar(
            select(func.count()).select_from(Player)
        ) or 0

        active_player_count = session.scalar(
            select(func.count())
            .select_from(Player)
            .where(Player.active.is_(True))
        ) or 0

        duplicate_ids = session.execute(
            select(
                Player.player_id,
                func.count().label("row_count"),
            )
            .group_by(Player.player_id)
            .having(func.count() > 1)
        ).all()

        missing_team = session.execute(
            select(
                Player.player_id,
                Player.full_name,
            )
            .where(Player.current_team_id.is_(None))
            .order_by(Player.full_name)
        ).all()

        invalid_team = session.execute(
            select(
                Player.player_id,
                Player.full_name,
                Player.current_team_id,
            )
            .outerjoin(
                Team,
                Player.current_team_id == Team.team_id,
            )
            .where(Player.current_team_id.is_not(None))
            .where(Team.team_id.is_(None))
        ).all()

        missing_handedness = session.scalar(
            select(func.count())
            .select_from(Player)
            .where(
                (Player.bats.is_(None))
                | (Player.throws.is_(None))
            )
        ) or 0

        team_counts = session.execute(
            select(
                Team.abbreviation,
                Team.name,
                func.count(Player.player_id).label(
                    "player_count"
                ),
            )
            .outerjoin(
                Player,
                Player.current_team_id == Team.team_id,
            )
            .where(Team.active.is_(True))
            .group_by(
                Team.team_id,
                Team.abbreviation,
                Team.name,
            )
            .order_by(Team.name)
        ).all()

        recent_runs = session.execute(
            select(
                CollectionRun.collection_run_id,
                CollectionRun.status,
                CollectionRun.records_read,
                CollectionRun.records_inserted,
                CollectionRun.records_updated,
                CollectionRun.records_rejected,
            )
            .where(
                CollectionRun.collector_name
                == "mlb_active_rosters"
            )
            .order_by(
                CollectionRun.collection_run_id.desc()
            )
            .limit(5)
        ).all()

    print(f"Stored players: {player_count}")
    print(f"Active players: {active_player_count}")
    print(f"Duplicate player IDs: {len(duplicate_ids)}")
    print(f"Players without team: {len(missing_team)}")
    print(f"Players with invalid team: {len(invalid_team)}")
    print(
        "Players missing batting or throwing hand: "
        f"{missing_handedness}"
    )

    print()
    print("Players per team:")

    for row in team_counts:
        print(
            f"{row.abbreviation or '---':<4} | "
            f"{row.name:<30} | "
            f"{row.player_count:>3}"
        )

    print()
    print("Recent player collection runs:")

    for run in recent_runs:
        print(
            f"Run {run.collection_run_id}: "
            f"status={run.status}, "
            f"read={run.records_read}, "
            f"inserted={run.records_inserted}, "
            f"updated={run.records_updated}, "
            f"rejected={run.records_rejected}"
        )

    failed = False

    if player_count == 0:
        print("\nFailure: no players were collected.")
        failed = True

    if duplicate_ids:
        print("\nFailure: duplicate player IDs exist.")
        failed = True

    if invalid_team:
        print("\nFailure: players reference missing teams.")
        failed = True

    if failed:
        return 1

    print("\nPlayer verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())