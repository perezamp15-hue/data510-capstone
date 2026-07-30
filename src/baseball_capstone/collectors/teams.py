"""Collect and store MLB team information."""

from __future__ import annotations
from baseball_capstone.database.models import CollectionRun, Team
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from baseball_capstone.collectors.client import MLBAPIClient, MLBAPIError
from baseball_capstone.collectors.run_tracking import (
    CollectionMetrics,
    complete_collection_run,
    fail_collection_run,
    start_collection_run,
)
from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import Team


LOGGER = logging.getLogger(__name__)

COLLECTOR_NAME = "mlb_teams"
MLB_SPORT_ID = 1


class TeamValidationError(ValueError):
    """Raised when a team record lacks required information."""


@dataclass(frozen=True, slots=True)
class TeamRecord:
    """Validated team data ready for PostgreSQL."""

    team_id: int
    name: str
    abbreviation: str | None
    league_name: str | None
    division_name: str | None
    active: bool

    def as_dict(self) -> dict[str, Any]:
        """Convert the record into database-compatible values."""
        return {
            "team_id": self.team_id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "league_name": self.league_name,
            "division_name": self.division_name,
            "active": self.active,
        }


def optional_text(value: Any) -> str | None:
    """Normalize optional text values."""
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def parse_team(raw_team: dict[str, Any]) -> TeamRecord:
    """Validate and normalize one MLB team object."""
    team_id = raw_team.get("id")
    team_name = optional_text(raw_team.get("name"))

    if not isinstance(team_id, int):
        raise TeamValidationError(
            f"Team has an invalid or missing id: {team_id!r}"
        )

    if not team_name:
        raise TeamValidationError(
            f"Team {team_id} has no valid name."
        )

    league = raw_team.get("league") or {}
    division = raw_team.get("division") or {}

    return TeamRecord(
        team_id=team_id,
        name=team_name,
        abbreviation=optional_text(raw_team.get("abbreviation")),
        league_name=optional_text(league.get("name")),
        division_name=optional_text(division.get("name")),
        active=bool(raw_team.get("active", True)),
    )


def fetch_teams(client: MLBAPIClient) -> list[dict[str, Any]]:
    """Fetch MLB teams from the Stats API."""
    payload = client.get_json(
        "/v1/teams",
        params={
            "sportId": MLB_SPORT_ID,
            "hydrate": "league,division",
        },
    )

    teams = payload.get("teams")

    if not isinstance(teams, list):
        raise MLBAPIError(
            "MLB teams response did not contain a valid 'teams' list."
        )

    return teams


def load_existing_team_ids(
    session: Session,
    team_ids: list[int],
) -> set[int]:
    """Return team IDs already stored in PostgreSQL."""
    if not team_ids:
        return set()

    statement = select(Team.team_id).where(
        Team.team_id.in_(team_ids)
    )

    return set(session.scalars(statement).all())


def upsert_teams(
    session: Session,
    team_records: list[TeamRecord],
) -> tuple[int, int]:
    """Insert new teams and update existing teams."""
    if not team_records:
        return 0, 0

    team_ids = [record.team_id for record in team_records]
    existing_team_ids = load_existing_team_ids(session, team_ids)

    values = [record.as_dict() for record in team_records]

    statement = insert(Team).values(values)

    statement = statement.on_conflict_do_update(
        index_elements=[Team.team_id],
        set_={
            "name": statement.excluded.name,
            "abbreviation": statement.excluded.abbreviation,
            "league_name": statement.excluded.league_name,
            "division_name": statement.excluded.division_name,
            "active": statement.excluded.active,
        },
    )

    session.execute(statement)

    inserted = sum(
        record.team_id not in existing_team_ids
        for record in team_records
    )
    updated = len(team_records) - inserted

    return inserted, updated


def collect_teams() -> CollectionMetrics:
    """Collect MLB teams and persist them to PostgreSQL."""
    metrics = CollectionMetrics()
    collection_run_id: int | None = None

    with session_scope() as session:
        collection_run = start_collection_run(
            session=session,
            collector_name=COLLECTOR_NAME,
        )
        collection_run_id = collection_run.collection_run_id

    try:
        with MLBAPIClient() as client:
            raw_teams = fetch_teams(client)

        metrics.records_read = len(raw_teams)

        validated_teams: list[TeamRecord] = []

        for raw_team in raw_teams:
            try:
                validated_teams.append(parse_team(raw_team))
            except TeamValidationError as exc:
                metrics.records_rejected += 1
                LOGGER.warning(
                    "Rejecting invalid team record: %s",
                    exc,
                )

        with session_scope() as session:
            inserted, updated = upsert_teams(
                session=session,
                team_records=validated_teams,
            )

            metrics.records_inserted = inserted
            metrics.records_updated = updated

            collection_run = session.get(
                CollectionRun,
                collection_run_id,
            )

            if collection_run is None:
                raise RuntimeError(
                    f"Collection run {collection_run_id} was not found."
                )

            complete_collection_run(
                collection_run=collection_run,
                metrics=metrics,
            )

        LOGGER.info(
            "Team collection completed: read=%s inserted=%s "
            "updated=%s rejected=%s",
            metrics.records_read,
            metrics.records_inserted,
            metrics.records_updated,
            metrics.records_rejected,
        )

        return metrics

    except Exception as exc:
        if collection_run_id is not None:
            with session_scope() as session:
                collection_run = session.get(
                    CollectionRun,
                    collection_run_id,
                )

                if collection_run is not None:
                    fail_collection_run(
                        collection_run=collection_run,
                        error=exc,
                        metrics=metrics,
                    )

        raise