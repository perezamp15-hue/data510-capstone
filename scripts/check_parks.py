"""Verify MLB parks and team-to-park assignments."""

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
    Park,
    Team,
)


def main() -> int:
    """Verify parks and team assignments."""
    with session_scope() as session:
        park_count = session.scalar(
            select(func.count()).select_from(Park)
        )

        duplicate_park_ids = session.execute(
            select(
                Park.park_id,
                func.count().label("row_count"),
            )
            .group_by(Park.park_id)
            .having(func.count() > 1)
        ).all()

        teams_without_parks = session.execute(
            select(
                Team.team_id,
                Team.name,
            )
            .where(Team.active.is_(True))
            .where(Team.current_park_id.is_(None))
            .order_by(Team.name)
        ).all()

        team_parks = session.execute(
            select(
                Team.team_id,
                Team.abbreviation,
                Team.name,
                Park.park_id,
                Park.name.label("park_name"),
                Park.city,
                Park.state,
                Park.time_zone,
            )
            .join(
                Park,
                Team.current_park_id == Park.park_id,
            )
            .order_by(Team.name)
        ).all()

        collection_runs = session.execute(
            select(
                CollectionRun.collection_run_id,
                CollectionRun.status,
                CollectionRun.records_read,
                CollectionRun.records_inserted,
                CollectionRun.records_updated,
                CollectionRun.records_rejected,
            )
            .where(
                CollectionRun.collector_name == "mlb_parks"
            )
            .order_by(
                CollectionRun.collection_run_id.desc()
            )
            .limit(5)
        ).all()

    print(f"Stored parks: {park_count}")
    print(f"Duplicate park IDs: {len(duplicate_park_ids)}")
    print(
        "Active teams without park assignments: "
        f"{len(teams_without_parks)}"
    )
    print()

    print("Team and park assignments:")

    for row in team_parks:
        location = ", ".join(
            value
            for value in [row.city, row.state]
            if value
        )

        print(
            f"{row.abbreviation or '---':<4} | "
            f"{row.name:<30} | "
            f"{row.park_name:<30} | "
            f"{location or 'Unknown location'}"
        )

    if teams_without_parks:
        print()
        print("Teams without park assignments:")

        for team_id, team_name in teams_without_parks:
            print(f"  - {team_id}: {team_name}")

    print()
    print("Recent park collection runs:")

    for run in collection_runs:
        print(
            f"Run {run.collection_run_id}: "
            f"status={run.status}, "
            f"read={run.records_read}, "
            f"inserted={run.records_inserted}, "
            f"updated={run.records_updated}, "
            f"rejected={run.records_rejected}"
        )

    if not park_count:
        print("\nVerification failed: no parks were stored.")
        return 1

    if duplicate_park_ids:
        print(
            "\nVerification failed: duplicate park IDs were found."
        )
        return 1

    if teams_without_parks:
        print(
            "\nVerification warning: some active teams "
            "do not have park assignments."
        )
        return 1

    print("\nPark verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())