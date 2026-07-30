"""Collect active MLB rosters and player profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
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
from baseball_capstone.database.models import (
    CollectionRun,
    Player,
    Team,
)


LOGGER = logging.getLogger(__name__)

COLLECTOR_NAME = "mlb_active_rosters"


class PlayerValidationError(ValueError):
    """Raised when a player record cannot be validated."""


@dataclass(frozen=True, slots=True)
class PlayerRecord:
    """Validated player information ready for PostgreSQL."""

    player_id: int
    full_name: str
    first_name: str | None
    last_name: str | None
    use_name: str | None
    primary_position: str | None
    position_name: str | None
    position_type: str | None
    bats: str | None
    throws: str | None
    birth_date: date | None
    mlb_debut_date: date | None
    height: str | None
    weight: int | None
    jersey_number: str | None
    active: bool
    roster_status: str | None
    current_team_id: int
    last_roster_check_at: datetime

    def as_dict(self) -> dict[str, Any]:
        """Convert the record to database values."""
        return {
            "player_id": self.player_id,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "use_name": self.use_name,
            "primary_position": self.primary_position,
            "position_name": self.position_name,
            "position_type": self.position_type,
            "bats": self.bats,
            "throws": self.throws,
            "birth_date": self.birth_date,
            "mlb_debut_date": self.mlb_debut_date,
            "height": self.height,
            "weight": self.weight,
            "jersey_number": self.jersey_number,
            "active": self.active,
            "roster_status": self.roster_status,
            "current_team_id": self.current_team_id,
            "last_roster_check_at": self.last_roster_check_at,
        }


def optional_text(value: Any) -> str | None:
    """Normalize an optional string."""
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


def optional_date(value: Any) -> date | None:
    """Convert an ISO date string into a date."""
    text = optional_text(value)

    if not text:
        return None

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        LOGGER.warning("Could not parse date value %r", value)
        return None


def fetch_team_roster(
    client: MLBAPIClient,
    team_id: int,
) -> list[dict[str, Any]]:
    """Fetch the current active roster for one team."""
    payload = client.get_json(
        f"/v1/teams/{team_id}/roster",
        params={
            "rosterType": "active",
            "hydrate": "person",
        },
    )

    roster = payload.get("roster")

    if not isinstance(roster, list):
        raise MLBAPIError(
            f"Team {team_id} response did not contain a roster list."
        )

    return roster


def fetch_player_profile(
    client: MLBAPIClient,
    player_id: int,
) -> dict[str, Any]:
    """Fetch the detailed profile for one player."""
    payload = client.get_json(
        f"/v1/people/{player_id}",
        params={
            "hydrate": "currentTeam",
        },
    )

    people = payload.get("people")

    if not isinstance(people, list) or not people:
        raise MLBAPIError(
            f"Player profile {player_id} was not returned."
        )

    person = people[0]

    if not isinstance(person, dict):
        raise MLBAPIError(
            f"Player profile {player_id} had an invalid format."
        )

    return person


def parse_player(
    roster_entry: dict[str, Any],
    profile: dict[str, Any],
    team_id: int,
) -> PlayerRecord:
    """Combine roster and person responses into one player record."""
    person = roster_entry.get("person") or {}

    player_id = profile.get("id") or person.get("id")
    full_name = optional_text(
        profile.get("fullName") or person.get("fullName")
    )

    if not isinstance(player_id, int):
        raise PlayerValidationError(
            f"Invalid player ID: {player_id!r}"
        )

    if not full_name:
        raise PlayerValidationError(
            f"Player {player_id} has no valid name."
        )

    position = (
        profile.get("primaryPosition")
        or roster_entry.get("position")
        or {}
    )

    bat_side = profile.get("batSide") or {}
    pitch_hand = profile.get("pitchHand") or {}
    status = roster_entry.get("status") or {}

    jersey_number = optional_text(
        roster_entry.get("jerseyNumber")
        or profile.get("primaryNumber")
    )

    return PlayerRecord(
        player_id=player_id,
        full_name=full_name,
        first_name=optional_text(profile.get("firstName")),
        last_name=optional_text(profile.get("lastName")),
        use_name=optional_text(profile.get("useName")),
        primary_position=optional_text(
            position.get("abbreviation")
            or position.get("code")
        ),
        position_name=optional_text(position.get("name")),
        position_type=optional_text(position.get("type")),
        bats=optional_text(
            bat_side.get("code") or bat_side.get("description")
        ),
        throws=optional_text(
            pitch_hand.get("code")
            or pitch_hand.get("description")
        ),
        birth_date=optional_date(profile.get("birthDate")),
        mlb_debut_date=optional_date(profile.get("mlbDebutDate")),
        height=optional_text(profile.get("height")),
        weight=optional_integer(profile.get("weight")),
        jersey_number=jersey_number,
        active=bool(profile.get("active", True)),
        roster_status=optional_text(
            status.get("code")
            or status.get("description")
        ),
        current_team_id=team_id,
        last_roster_check_at=datetime.now(timezone.utc),
    )


def load_active_team_ids(session: Session) -> list[int]:
    """Return active MLB team IDs from PostgreSQL."""
    statement = (
        select(Team.team_id)
        .where(Team.active.is_(True))
        .order_by(Team.team_id)
    )

    return list(session.scalars(statement).all())


def load_existing_player_ids(
    session: Session,
    player_ids: list[int],
) -> set[int]:
    """Return player IDs already stored in PostgreSQL."""
    if not player_ids:
        return set()

    statement = select(Player.player_id).where(
        Player.player_id.in_(player_ids)
    )

    return set(session.scalars(statement).all())


def deduplicate_players(
    records: list[PlayerRecord],
) -> list[PlayerRecord]:
    """Keep one record for each player ID."""
    by_player_id: dict[int, PlayerRecord] = {}

    for record in records:
        by_player_id[record.player_id] = record

    return list(by_player_id.values())


def upsert_players(
    session: Session,
    player_records: list[PlayerRecord],
) -> tuple[int, int]:
    """Insert new players and update existing players."""
    player_records = deduplicate_players(player_records)

    if not player_records:
        return 0, 0

    player_ids = [
        record.player_id
        for record in player_records
    ]

    existing_ids = load_existing_player_ids(
        session,
        player_ids,
    )

    statement = insert(Player).values(
        [record.as_dict() for record in player_records]
    )

    statement = statement.on_conflict_do_update(
        index_elements=[Player.player_id],
        set_={
            "full_name": statement.excluded.full_name,
            "first_name": statement.excluded.first_name,
            "last_name": statement.excluded.last_name,
            "use_name": statement.excluded.use_name,
            "primary_position": statement.excluded.primary_position,
            "position_name": statement.excluded.position_name,
            "position_type": statement.excluded.position_type,
            "bats": statement.excluded.bats,
            "throws": statement.excluded.throws,
            "birth_date": statement.excluded.birth_date,
            "mlb_debut_date": statement.excluded.mlb_debut_date,
            "height": statement.excluded.height,
            "weight": statement.excluded.weight,
            "jersey_number": statement.excluded.jersey_number,
            "active": statement.excluded.active,
            "roster_status": statement.excluded.roster_status,
            "current_team_id": statement.excluded.current_team_id,
            "last_roster_check_at": (
                statement.excluded.last_roster_check_at
            ),
        },
    )

    session.execute(statement)

    inserted = sum(
        record.player_id not in existing_ids
        for record in player_records
    )

    updated = len(player_records) - inserted

    return inserted, updated


def collect_players() -> CollectionMetrics:
    """Collect active rosters and player profiles."""
    metrics = CollectionMetrics()
    collection_run_id: int | None = None

    with session_scope() as session:
        team_ids = load_active_team_ids(session)

        if not team_ids:
            raise RuntimeError(
                "No active teams were found. Run collect_teams.py first."
            )

        collection_run = start_collection_run(
            session=session,
            collector_name=COLLECTOR_NAME,
        )

        collection_run_id = collection_run.collection_run_id

    try:
        player_records: list[PlayerRecord] = []

        with MLBAPIClient() as client:
            for team_id in team_ids:
                LOGGER.info(
                    "Collecting active roster for team %s",
                    team_id,
                )

                roster = fetch_team_roster(
                    client=client,
                    team_id=team_id,
                )

                metrics.records_read += len(roster)

                for roster_entry in roster:
                    person = roster_entry.get("person") or {}
                    player_id = person.get("id")

                    if not isinstance(player_id, int):
                        metrics.records_rejected += 1
                        LOGGER.warning(
                            "Skipping roster entry without player ID."
                        )
                        continue

                    try:
                        profile = fetch_player_profile(
                            client=client,
                            player_id=player_id,
                        )

                        player_records.append(
                            parse_player(
                                roster_entry=roster_entry,
                                profile=profile,
                                team_id=team_id,
                            )
                        )
                    except (
                        MLBAPIError,
                        PlayerValidationError,
                    ) as exc:
                        metrics.records_rejected += 1
                        LOGGER.warning(
                            "Rejecting player %s: %s",
                            player_id,
                            exc,
                        )

        with session_scope() as session:
            inserted, updated = upsert_players(
                session=session,
                player_records=player_records,
            )

            metrics.records_inserted = inserted
            metrics.records_updated = updated

            collection_run = session.get(
                CollectionRun,
                collection_run_id,
            )

            if collection_run is None:
                raise RuntimeError(
                    f"Collection run {collection_run_id} "
                    "was not found."
                )

            complete_collection_run(
                collection_run=collection_run,
                metrics=metrics,
            )

        LOGGER.info(
            "Player collection completed: "
            "read=%s inserted=%s updated=%s rejected=%s",
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