"""Verify collected MLB games."""

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
    Game,
    Park,
    Player,
    Team,
)


def main() -> int:
    """Validate stored schedule data."""
    with session_scope() as session:
        game_count = session.scalar(
            select(func.count()).select_from(Game)
        ) or 0

        duplicate_ids = session.execute(
            select(
                Game.game_pk,
                func.count().label("row_count"),
            )
            .group_by(Game.game_pk)
            .having(func.count() > 1)
        ).all()

        invalid_home_teams = session.execute(
            select(Game.game_pk, Game.home_team_id)
            .outerjoin(
                Team,
                Game.home_team_id == Team.team_id,
            )
            .where(Team.team_id.is_(None))
        ).all()

        invalid_away_teams = session.execute(
            select(Game.game_pk, Game.away_team_id)
            .outerjoin(
                Team,
                Game.away_team_id == Team.team_id,
            )
            .where(Team.team_id.is_(None))
        ).all()

        games = session.execute(
            select(
                Game.game_pk,
                Game.game_date,
                Game.scheduled_start,
                Game.detailed_status,
                Game.away_score,
                Game.home_score,
                Team.name.label("home_team"),
            )
            .join(
                Team,
                Game.home_team_id == Team.team_id,
            )
            .order_by(
                Game.game_date.desc(),
                Game.scheduled_start.desc(),
            )
            .limit(25)
        ).all()

        recent_runs = session.execute(
            select(
                CollectionRun.collection_run_id,
                CollectionRun.status,
                CollectionRun.requested_start_date,
                CollectionRun.requested_end_date,
                CollectionRun.records_read,
                CollectionRun.records_inserted,
                CollectionRun.records_updated,
                CollectionRun.records_rejected,
            )
            .where(
                CollectionRun.collector_name == "mlb_schedule"
            )
            .order_by(
                CollectionRun.collection_run_id.desc()
            )
            .limit(5)
        ).all()

    print(f"Stored games: {game_count}")
    print(f"Duplicate game IDs: {len(duplicate_ids)}")
    print(
        "Games with invalid home teams: "
        f"{len(invalid_home_teams)}"
    )
    print(
        "Games with invalid away teams: "
        f"{len(invalid_away_teams)}"
    )

    print()
    print("Recent stored games:")

    for game in games:
        away_score = (
            "-" if game.away_score is None else game.away_score
        )
        home_score = (
            "-" if game.home_score is None else game.home_score
        )

        print(
            f"{game.game_pk} | "
            f"{game.game_date} | "
            f"{game.detailed_status or 'Unknown':<18} | "
            f"{away_score}-{home_score} | "
            f"Home: {game.home_team}"
        )

    print()
    print("Recent schedule collection runs:")

    for run in recent_runs:
        print(
            f"Run {run.collection_run_id}: "
            f"{run.requested_start_date} to "
            f"{run.requested_end_date}, "
            f"status={run.status}, "
            f"read={run.records_read}, "
            f"inserted={run.records_inserted}, "
            f"updated={run.records_updated}, "
            f"rejected={run.records_rejected}"
        )

    failed = False

    if game_count == 0:
        print("\nFailure: no games were stored.")
        failed = True

    if duplicate_ids:
        print("\nFailure: duplicate game IDs were found.")
        failed = True

    if invalid_home_teams or invalid_away_teams:
        print("\nFailure: games reference missing teams.")
        failed = True

    if failed:
        return 1

    print("\nGame verification succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())