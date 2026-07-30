"""Verify collected MLB team data."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func, select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import CollectionRun, Team


def main() -> int:
    """Display team and collection-run verification results."""
    with session_scope() as session:
        team_count = session.scalar(
            select(func.count()).select_from(Team)
        )

        duplicate_team_ids = session.execute(
            select(
                Team.team_id,
                func.count().label("row_count"),
            )
            .group_by(Team.team_id)
            .having(func.count() > 1)
        ).all()

        teams = session.execute(
            select(
                Team.team_id,
                Team.name,
                Team.abbreviation,
                Team.league_name,
                Team.division_name,
                Team.active,
            ).order_by(Team.name)
        ).all()

        collection_runs = session.execute(
            select(
                CollectionRun.collection_run_id,
                CollectionRun.status,
                CollectionRun.records_read,
                CollectionRun.records_inserted,
                CollectionRun.records_updated,
                CollectionRun.records_rejected,
                CollectionRun.started_at,
                CollectionRun.completed_at,
            )
            .where(CollectionRun.collector_name == "mlb_teams")
            .order_by(
                CollectionRun.collection_run_id.desc()
            )
            .limit(5)
        ).all()

    print(f"Stored teams: {team_count}")
    print(f"Duplicate team IDs: {len(duplicate_team_ids)}")
    print()

    print("Teams:")
    for team in teams:
        print(
            f"{team.team_id:>3} | "
            f"{team.abbreviation or '---':<4} | "
            f"{team.name:<30} | "
            f"{team.league_name or 'Unknown'} | "
            f"{team.division_name or 'Unknown'}"
        )

    print()
    print("Recent team collection runs:")

    for run in collection_runs:
        print(
            f"Run {run.collection_run_id}: "
            f"status={run.status}, "
            f"read={run.records_read}, "
            f"inserted={run.records_inserted}, "
            f"updated={run.records_updated}, "
            f"rejected={run.records_rejected}"
        )

    if not team_count:
        print("\nVerification failed: no teams were stored.")
        return 1

    if duplicate_team_ids:
        print("\nVerification failed: duplicate IDs were found.")
        return 1

    print("\nTeam verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())