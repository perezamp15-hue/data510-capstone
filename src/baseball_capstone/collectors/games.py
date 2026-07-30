"""Collect MLB schedules and game information."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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
    Game,
    Park,
    Player,
    Team,
)


LOGGER = logging.getLogger(__name__)

COLLECTOR_NAME = "mlb_schedule"
MLB_SPORT_ID = 1


class GameValidationError(ValueError):
    """Raised when a game cannot be validated."""


@dataclass(frozen=True, slots=True)
class GameRecord:
    """Validated schedule record ready for PostgreSQL."""

    game_pk: int
    game_date: date
    scheduled_start: datetime | None
    season: int
    game_type: str | None
    status: str | None
    detailed_status: str | None
    abstract_status: str | None
    doubleheader: str | None
    game_number: int | None
    home_team_id: int
    away_team_id: int
    park_id: int | None
    home_probable_pitcher_id: int | None
    away_probable_pitcher_id: int | None
    home_score: int | None
    away_score: int | None
    inning: int | None
    inning_half: str | None
    day_night: str | None
    temperature_f: int | None
    wind_speed_mph: int | None
    wind_direction: str | None
    weather_condition: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return database-compatible values."""
        return {
            "game_pk": self.game_pk,
            "game_date": self.game_date,
            "scheduled_start": self.scheduled_start,
            "season": self.season,
            "game_type": self.game_type,
            "status": self.status,
            "detailed_status": self.detailed_status,
            "abstract_status": self.abstract_status,
            "doubleheader": self.doubleheader,
            "game_number": self.game_number,
            "home_team_id": self.home_team_id,
            "away_team_id": self.away_team_id,
            "park_id": self.park_id,
            "home_probable_pitcher_id": self.home_probable_pitcher_id,
            "away_probable_pitcher_id": self.away_probable_pitcher_id,
            "home_score": self.home_score,
            "away_score": self.away_score,
            "inning": self.inning,
            "inning_half": self.inning_half,
            "day_night": self.day_night,
            "temperature_f": self.temperature_f,
            "wind_speed_mph": self.wind_speed_mph,
            "wind_direction": self.wind_direction,
            "weather_condition": self.weather_condition,
        }


def optional_text(value: Any) -> str | None:
    """Normalize optional text."""
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


def parse_iso_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 datetime returned by MLB."""
    text = optional_text(value)

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except ValueError:
        LOGGER.warning("Unable to parse datetime %r", value)
        return None


def parse_game_date(
    raw_date: Any,
    scheduled_start: datetime | None,
) -> date:
    """Parse the official game date."""
    text = optional_text(raw_date)

    if text:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass

    if scheduled_start is not None:
        return scheduled_start.date()

    raise GameValidationError("Game has no valid date.")


def parse_wind(weather: dict[str, Any]) -> tuple[int | None, str | None]:
    """Parse wind speed and direction from the weather object."""
    wind_text = optional_text(weather.get("wind"))

    if not wind_text:
        return None, None

    match = re.search(r"(\d+)", wind_text)
    speed = int(match.group(1)) if match else None

    direction: str | None = None

    if "," in wind_text:
        direction = optional_text(wind_text.split(",", 1)[1])
    elif speed is not None:
        direction = optional_text(
            re.sub(r"\d+\s*mph", "", wind_text, flags=re.I)
        )

    return speed, direction


def fetch_schedule(
    client: MLBAPIClient,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """Fetch MLB games for an inclusive date range."""
    payload = client.get_json(
        "/v1/schedule",
        params={
            "sportId": MLB_SPORT_ID,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "hydrate": (
                "team,venue,probablePitcher,"
                "linescore,weather"
            ),
        },
    )

    dates = payload.get("dates")

    if not isinstance(dates, list):
        raise MLBAPIError(
            "Schedule response did not contain a valid dates list."
        )

    games: list[dict[str, Any]] = []

    for date_group in dates:
        if not isinstance(date_group, dict):
            continue

        date_games = date_group.get("games")

        if isinstance(date_games, list):
            games.extend(
                game
                for game in date_games
                if isinstance(game, dict)
            )

    return games


def parse_game(raw_game: dict[str, Any]) -> GameRecord:
    """Normalize one MLB schedule game."""
    game_pk = raw_game.get("gamePk")

    if not isinstance(game_pk, int):
        raise GameValidationError(
            f"Invalid gamePk: {game_pk!r}"
        )

    scheduled_start = parse_iso_datetime(
        raw_game.get("gameDate")
    )

    official_date = parse_game_date(
        raw_game.get("officialDate"),
        scheduled_start,
    )

    season = optional_integer(raw_game.get("season"))

    if season is None:
        season = official_date.year

    teams = raw_game.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}

    home_team = home.get("team") or {}
    away_team = away.get("team") or {}

    home_team_id = home_team.get("id")
    away_team_id = away_team.get("id")

    if not isinstance(home_team_id, int):
        raise GameValidationError(
            f"Game {game_pk} has no valid home team."
        )

    if not isinstance(away_team_id, int):
        raise GameValidationError(
            f"Game {game_pk} has no valid away team."
        )

    venue = raw_game.get("venue") or {}
    park_id = venue.get("id")

    if not isinstance(park_id, int):
        park_id = None

    home_probable = home.get("probablePitcher") or {}
    away_probable = away.get("probablePitcher") or {}

    home_probable_pitcher_id = home_probable.get("id")
    away_probable_pitcher_id = away_probable.get("id")

    if not isinstance(home_probable_pitcher_id, int):
        home_probable_pitcher_id = None

    if not isinstance(away_probable_pitcher_id, int):
        away_probable_pitcher_id = None

    status = raw_game.get("status") or {}
    linescore = raw_game.get("linescore") or {}
    weather = raw_game.get("weather") or {}

    wind_speed, wind_direction = parse_wind(weather)

    return GameRecord(
        game_pk=game_pk,
        game_date=official_date,
        scheduled_start=scheduled_start,
        season=season,
        game_type=optional_text(raw_game.get("gameType")),
        status=optional_text(status.get("statusCode")),
        detailed_status=optional_text(
            status.get("detailedState")
        ),
        abstract_status=optional_text(
            status.get("abstractGameState")
        ),
        doubleheader=optional_text(
            raw_game.get("doubleHeader")
        ),
        game_number=optional_integer(
            raw_game.get("gameNumber")
        ),
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        park_id=park_id,
        home_probable_pitcher_id=home_probable_pitcher_id,
        away_probable_pitcher_id=away_probable_pitcher_id,
        home_score=optional_integer(home.get("score")),
        away_score=optional_integer(away.get("score")),
        inning=optional_integer(
            linescore.get("currentInning")
        ),
        inning_half=optional_text(
            linescore.get("inningHalf")
        ),
        day_night=optional_text(raw_game.get("dayNight")),
        temperature_f=optional_integer(
            weather.get("temp")
        ),
        wind_speed_mph=wind_speed,
        wind_direction=wind_direction,
        weather_condition=optional_text(
            weather.get("condition")
        ),
    )


def load_existing_game_ids(
    session: Session,
    game_ids: list[int],
) -> set[int]:
    """Return game IDs already stored."""
    if not game_ids:
        return set()

    statement = select(Game.game_pk).where(
        Game.game_pk.in_(game_ids)
    )

    return set(session.scalars(statement).all())


def load_reference_ids(
    session: Session,
) -> tuple[set[int], set[int], set[int]]:
    """Load valid team, park, and player IDs."""
    team_ids = set(
        session.scalars(select(Team.team_id)).all()
    )

    park_ids = set(
        session.scalars(select(Park.park_id)).all()
    )

    player_ids = set(
        session.scalars(select(Player.player_id)).all()
    )

    return team_ids, park_ids, player_ids


def sanitize_references(
    record: GameRecord,
    team_ids: set[int],
    park_ids: set[int],
    player_ids: set[int],
) -> GameRecord:
    """Remove optional foreign keys that are not stored locally."""
    if record.home_team_id not in team_ids:
        raise GameValidationError(
            f"Game {record.game_pk} references missing home team "
            f"{record.home_team_id}."
        )

    if record.away_team_id not in team_ids:
        raise GameValidationError(
            f"Game {record.game_pk} references missing away team "
            f"{record.away_team_id}."
        )

    values = record.as_dict()

    if record.park_id not in park_ids:
        values["park_id"] = None

    if record.home_probable_pitcher_id not in player_ids:
        values["home_probable_pitcher_id"] = None

    if record.away_probable_pitcher_id not in player_ids:
        values["away_probable_pitcher_id"] = None

    return GameRecord(**values)


def deduplicate_games(
    game_records: list[GameRecord],
) -> list[GameRecord]:
    """Keep one record per gamePk."""
    records_by_id: dict[int, GameRecord] = {}

    for record in game_records:
        records_by_id[record.game_pk] = record

    return list(records_by_id.values())


def upsert_games(
    session: Session,
    game_records: list[GameRecord],
) -> tuple[int, int]:
    """Insert new games and update existing games."""
    game_records = deduplicate_games(game_records)

    if not game_records:
        return 0, 0

    game_ids = [
        record.game_pk
        for record in game_records
    ]

    existing_ids = load_existing_game_ids(
        session,
        game_ids,
    )

    statement = insert(Game).values(
        [record.as_dict() for record in game_records]
    )

    statement = statement.on_conflict_do_update(
        index_elements=[Game.game_pk],
        set_={
            "game_date": statement.excluded.game_date,
            "scheduled_start": statement.excluded.scheduled_start,
            "season": statement.excluded.season,
            "game_type": statement.excluded.game_type,
            "status": statement.excluded.status,
            "detailed_status": statement.excluded.detailed_status,
            "abstract_status": statement.excluded.abstract_status,
            "doubleheader": statement.excluded.doubleheader,
            "game_number": statement.excluded.game_number,
            "home_team_id": statement.excluded.home_team_id,
            "away_team_id": statement.excluded.away_team_id,
            "park_id": statement.excluded.park_id,
            "home_probable_pitcher_id": (
                statement.excluded.home_probable_pitcher_id
            ),
            "away_probable_pitcher_id": (
                statement.excluded.away_probable_pitcher_id
            ),
            "home_score": statement.excluded.home_score,
            "away_score": statement.excluded.away_score,
            "inning": statement.excluded.inning,
            "inning_half": statement.excluded.inning_half,
            "day_night": statement.excluded.day_night,
            "temperature_f": statement.excluded.temperature_f,
            "wind_speed_mph": statement.excluded.wind_speed_mph,
            "wind_direction": statement.excluded.wind_direction,
            "weather_condition": (
                statement.excluded.weather_condition
            ),
        },
    )

    session.execute(statement)

    inserted = sum(
        record.game_pk not in existing_ids
        for record in game_records
    )

    updated = len(game_records) - inserted

    return inserted, updated


def collect_games(
    start_date: date,
    end_date: date,
) -> CollectionMetrics:
    """Collect schedule data for an inclusive date range."""
    if end_date < start_date:
        raise ValueError(
            "end_date cannot be earlier than start_date."
        )

    if (end_date - start_date).days > 31:
        raise ValueError(
            "A single schedule collection run cannot exceed "
            "32 calendar days."
        )

    metrics = CollectionMetrics()
    collection_run_id: int | None = None

    with session_scope() as session:
        collection_run = start_collection_run(
            session=session,
            collector_name=COLLECTOR_NAME,
            requested_start_date=start_date,
            requested_end_date=end_date,
        )

        collection_run_id = collection_run.collection_run_id

    try:
        with MLBAPIClient() as client:
            raw_games = fetch_schedule(
                client=client,
                start_date=start_date,
                end_date=end_date,
            )

        metrics.records_read = len(raw_games)

        parsed_records: list[GameRecord] = []

        with session_scope() as session:
            team_ids, park_ids, player_ids = load_reference_ids(
                session
            )

        for raw_game in raw_games:
            try:
                record = parse_game(raw_game)

                record = sanitize_references(
                    record=record,
                    team_ids=team_ids,
                    park_ids=park_ids,
                    player_ids=player_ids,
                )

                parsed_records.append(record)

            except GameValidationError as exc:
                metrics.records_rejected += 1
                LOGGER.warning(
                    "Rejecting game record: %s",
                    exc,
                )

        with session_scope() as session:
            inserted, updated = upsert_games(
                session=session,
                game_records=parsed_records,
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
            "Game collection completed: "
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