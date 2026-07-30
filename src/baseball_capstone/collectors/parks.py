"""Collect MLB parks and connect teams to their current venues."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from baseball_capstone.collectors.client import (
    MLBAPIClient,
    MLBAPIError,
)
from baseball_capstone.collectors.run_tracking import (
    CollectionMetrics,
    complete_collection_run,
    fail_collection_run,
    start_collection_run,
)
from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import (
    CollectionRun,
    Park,
    Team,
)


LOGGER = logging.getLogger(__name__)

COLLECTOR_NAME = "mlb_parks"
MLB_SPORT_ID = 1


class ParkValidationError(ValueError):
    """Raised when a park record is missing required information."""


@dataclass(frozen=True, slots=True)
class ParkRecord:
    """Validated MLB park information."""

    park_id: int
    name: str
    city: str | None
    state: str | None
    country: str | None
    time_zone: str | None
    elevation_feet: int | None

    def as_dict(self) -> dict[str, Any]:
        """Convert this record to database-compatible values."""
        return {
            "park_id": self.park_id,
            "name": self.name,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "time_zone": self.time_zone,
            "elevation_feet": self.elevation_feet,
        }


@dataclass(frozen=True, slots=True)
class TeamParkAssignment:
    """Connection between a team and its current venue."""

    team_id: int
    park_id: int


def optional_text(value: Any) -> str | None:
    """Normalize optional string values."""
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def optional_integer(value: Any) -> int | None:
    """Convert an optional value to an integer."""
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_team_venues(
    client: MLBAPIClient,
) -> list[dict[str, Any]]:
    """Fetch active MLB teams with hydrated venue information."""
    payload = client.get_json(
        "/v1/teams",
        params={
            "sportId": MLB_SPORT_ID,
            "hydrate": "venue",
        },
    )

    teams = payload.get("teams")

    if not isinstance(teams, list):
        raise MLBAPIError(
            "MLB response did not contain a valid 'teams' list."
        )

    return teams


def parse_team_park(
    raw_team: dict[str, Any],
) -> tuple[ParkRecord, TeamParkAssignment]:
    """Parse one team and its current venue."""
    team_id = raw_team.get("id")

    if not isinstance(team_id, int):
        raise ParkValidationError(
            f"Team has an invalid ID: {team_id!r}"
        )

    venue = raw_team.get("venue")

    if not isinstance(venue, dict):
        raise ParkValidationError(
            f"Team {team_id} has no valid venue object."
        )

    park_id = venue.get("id")
    park_name = optional_text(venue.get("name"))

    if not isinstance(park_id, int):
        raise ParkValidationError(
            f"Team {team_id} has an invalid venue ID: {park_id!r}"
        )

    if not park_name:
        raise ParkValidationError(
            f"Venue {park_id} has no valid name."
        )

    location = venue.get("location") or {}
    time_zone = venue.get("timeZone") or {}
    field_info = venue.get("fieldInfo") or {}

    elevation = (
        location.get("elevation")
        or field_info.get("elevation")
        or venue.get("elevation")
    )

    park_record = ParkRecord(
        park_id=park_id,
        name=park_name,
        city=optional_text(location.get("city")),
        state=optional_text(
            location.get("stateAbbrev")
            or location.get("state")
        ),
        country=optional_text(location.get("country")),
        time_zone=optional_text(
            time_zone.get("id")
            or time_zone.get("tz")
        ),
        elevation_feet=optional_integer(elevation),
    )

    assignment = TeamParkAssignment(
        team_id=team_id,
        park_id=park_id,
    )

    return park_record, assignment


def load_existing_park_ids(
    session: Session,
    park_ids: list[int],
) -> set[int]:
    """Return park IDs already stored in PostgreSQL."""
    if not park_ids:
        return set()

    statement = select(Park.park_id).where(
        Park.park_id.in_(park_ids)
    )

    return set(session.scalars(statement).all())


def deduplicate_parks(
    park_records: list[ParkRecord],
) -> list[ParkRecord]:
    """Keep one park record per park ID."""
    records_by_id: dict[int, ParkRecord] = {}

    for record in park_records:
        records_by_id[record.park_id] = record

    return list(records_by_id.values())


def upsert_parks(
    session: Session,
    park_records: list[ParkRecord],
) -> tuple[int, int]:
    """Insert new parks and update existing parks."""
    park_records = deduplicate_parks(park_records)

    if not park_records:
        return 0, 0

    park_ids = [record.park_id for record in park_records]
    existing_park_ids = load_existing_park_ids(
        session=session,
        park_ids=park_ids,
    )

    values = [record.as_dict() for record in park_records]

    statement = insert(Park).values(values)

    statement = statement.on_conflict_do_update(
        index_elements=[Park.park_id],
        set_={
            "name": statement.excluded.name,
            "city": statement.excluded.city,
            "state": statement.excluded.state,
            "country": statement.excluded.country,
            "time_zone": statement.excluded.time_zone,
            "elevation_feet": statement.excluded.elevation_feet,
        },
    )

    session.execute(statement)

    inserted = sum(
        record.park_id not in existing_park_ids
        for record in park_records
    )
    updated = len(park_records) - inserted

    return inserted, updated


def assign_team_parks(
    session: Session,
    assignments: list[TeamParkAssignment],
) -> tuple[int, int]:
    """
    Update teams with current park IDs.

    Returns:
        A tuple containing:
        - number of teams changed;
        - number of assignments skipped.
    """
    changed = 0
    skipped = 0

    for assignment in assignments:
        team = session.get(Team, assignment.team_id)

        if team is None:
            LOGGER.warning(
                "Cannot assign park %s because team %s is missing.",
                assignment.park_id,
                assignment.team_id,
            )
            skipped += 1
            continue

        if team.current_park_id != assignment.park_id:
            team.current_park_id = assignment.park_id
            changed += 1

    return changed, skipped


def collect_parks() -> CollectionMetrics:
    """Collect parks and assign each team its current venue."""
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
            raw_teams = fetch_team_venues(client)

        metrics.records_read = len(raw_teams)

        park_records: list[ParkRecord] = []
        assignments: list[TeamParkAssignment] = []

        for raw_team in raw_teams:
            try:
                park_record, assignment = parse_team_park(raw_team)
                park_records.append(park_record)
                assignments.append(assignment)
            except ParkValidationError as exc:
                metrics.records_rejected += 1
                LOGGER.warning(
                    "Rejecting invalid team venue record: %s",
                    exc,
                )

        with session_scope() as session:
            inserted, updated = upsert_parks(
                session=session,
                park_records=park_records,
            )

            changed_assignments, skipped_assignments = (
                assign_team_parks(
                    session=session,
                    assignments=assignments,
                )
            )

            metrics.records_inserted = inserted
            metrics.records_updated = updated
            metrics.records_rejected += skipped_assignments

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
            "Park collection completed: read=%s inserted=%s "
            "updated=%s assignments_changed=%s rejected=%s",
            metrics.records_read,
            metrics.records_inserted,
            metrics.records_updated,
            changed_assignments,
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