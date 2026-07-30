"""Restartable, low-memory MLB pitch-by-pitch collector."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from baseball_capstone.collectors.client import MLBAPIClient
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
    Pitch,
    Player,
)


LOGGER = logging.getLogger(__name__)
COLLECTOR_NAME = "mlb_pitch_feed"


class PitchValidationError(ValueError):
    """Raised when a pitch cannot be validated."""


@dataclass(frozen=True, slots=True)
class PitchRecord:
    """Validated pitch values ready for PostgreSQL."""

    game_pk: int
    game_date: date
    at_bat_number: int
    plate_appearance_number: int | None
    pitch_number: int
    inning: int | None
    inning_half: str | None
    outs: int | None
    balls: int | None
    strikes: int | None
    pitcher_id: int
    batter_id: int
    pitch_type: str | None
    pitch_name: str | None
    description: str | None
    event: str | None
    event_type: str | None
    is_pitch: bool
    is_ball: bool | None
    is_strike: bool | None
    is_in_play: bool | None
    release_speed: Decimal | None
    effective_speed: Decimal | None
    release_spin_rate: int | None
    release_extension: Decimal | None
    release_pos_x: Decimal | None
    release_pos_y: Decimal | None
    release_pos_z: Decimal | None
    plate_x: Decimal | None
    plate_z: Decimal | None
    strike_zone_top: Decimal | None
    strike_zone_bottom: Decimal | None
    pfx_x: Decimal | None
    pfx_z: Decimal | None
    launch_speed: Decimal | None
    launch_angle: Decimal | None
    hit_distance: Decimal | None
    hit_location: int | None
    trajectory: str | None
    hardness: str | None
    estimated_batting_average: Decimal | None
    estimated_woba: Decimal | None
    estimated_slugging: Decimal | None
    zone: int | None
    type_code: str | None
    runner_on_first: bool
    runner_on_second: bool
    runner_on_third: bool
    home_score: int | None
    away_score: int | None
    raw_payload: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            field_name: getattr(self, field_name)
            for field_name in self.__dataclass_fields__
        }


def optional_text(value: Any) -> str | None:
    if value is None:
        return None

    result = str(value).strip()
    return result or None


def optional_integer(value: Any) -> int | None:
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def fetch_game_feed(
    client: MLBAPIClient,
    game_pk: int,
) -> dict[str, Any]:
    """Fetch one game live-feed payload."""
    return client.get_json(
        f"/v1.1/game/{game_pk}/feed/live"
    )


def extract_game_date(
    feed: dict[str, Any],
    fallback_date: date,
) -> date:
    """Extract the official date from game metadata."""
    game_data = feed.get("gameData") or {}
    datetime_data = game_data.get("datetime") or {}

    official_date = optional_text(
        datetime_data.get("officialDate")
    )

    if official_date:
        try:
            return date.fromisoformat(official_date[:10])
        except ValueError:
            pass

    return fallback_date


def extract_player_name(
    feed: dict[str, Any],
    player_id: int,
) -> str:
    """Return a player name or a safe placeholder."""
    game_data = feed.get("gameData") or {}
    players = game_data.get("players") or {}

    player = players.get(f"ID{player_id}") or {}

    return (
        optional_text(player.get("fullName"))
        or f"MLB Player {player_id}"
    )


def ensure_player(
    session: Session,
    player_id: int,
    full_name: str,
) -> None:
    """Create a minimal player record when not already stored."""
    statement = insert(Player).values(
        player_id=player_id,
        full_name=full_name,
        active=True,
    )

    statement = statement.on_conflict_do_nothing(
        index_elements=[Player.player_id]
    )

    session.execute(statement)


def parse_pitch(
    *,
    game_pk: int,
    game_date: date,
    at_bat: dict[str, Any],
    play_event: dict[str, Any],
) -> PitchRecord:
    """Parse one pitch event from a game feed."""
    about = at_bat.get("about") or {}
    matchup = at_bat.get("matchup") or {}
    result = at_bat.get("result") or {}
    count = play_event.get("count") or {}
    details = play_event.get("details") or {}
    pitch_data = play_event.get("pitchData") or {}
    coordinates = pitch_data.get("coordinates") or {}
    breaks = pitch_data.get("breaks") or {}
    hit_data = play_event.get("hitData") or {}
    hit_coordinates = hit_data.get("coordinates") or {}
    runners = at_bat.get("runners") or []

    at_bat_number = optional_integer(about.get("atBatIndex"))
    pitch_number = optional_integer(play_event.get("pitchNumber"))

    pitcher = matchup.get("pitcher") or {}
    batter = matchup.get("batter") or {}

    pitcher_id = pitcher.get("id")
    batter_id = batter.get("id")

    if at_bat_number is None:
        raise PitchValidationError("Missing at-bat index.")

    if pitch_number is None:
        raise PitchValidationError(
            f"At-bat {at_bat_number} is missing pitch number."
        )

    if not isinstance(pitcher_id, int):
        raise PitchValidationError(
            f"At-bat {at_bat_number} has no pitcher ID."
        )

    if not isinstance(batter_id, int):
        raise PitchValidationError(
            f"At-bat {at_bat_number} has no batter ID."
        )

    pitch_type = details.get("type") or {}
    call = details.get("call") or {}

    runner_bases = {
        optional_text(
            (runner.get("movement") or {}).get("start")
        )
        for runner in runners
        if isinstance(runner, dict)
    }

    raw_payload = json.dumps(
        play_event,
        separators=(",", ":"),
        default=str,
    )

    return PitchRecord(
        game_pk=game_pk,
        game_date=game_date,
        at_bat_number=at_bat_number,
        plate_appearance_number=at_bat_number + 1,
        pitch_number=pitch_number,
        inning=optional_integer(about.get("inning")),
        inning_half=optional_text(about.get("halfInning")),
        outs=optional_integer(count.get("outs")),
        balls=optional_integer(count.get("balls")),
        strikes=optional_integer(count.get("strikes")),
        pitcher_id=pitcher_id,
        batter_id=batter_id,
        pitch_type=optional_text(pitch_type.get("code")),
        pitch_name=optional_text(pitch_type.get("description")),
        description=optional_text(details.get("description")),
        event=optional_text(result.get("event")),
        event_type=optional_text(result.get("eventType")),
        is_pitch=True,
        is_ball=details.get("isBall"),
        is_strike=details.get("isStrike"),
        is_in_play=details.get("isInPlay"),
        release_speed=optional_decimal(
            pitch_data.get("startSpeed")
        ),
        effective_speed=optional_decimal(
            pitch_data.get("effectiveSpeed")
        ),
        release_spin_rate=optional_integer(
            breaks.get("spinRate")
        ),
        release_extension=optional_decimal(
            pitch_data.get("extension")
        ),
        release_pos_x=optional_decimal(
            coordinates.get("x0")
        ),
        release_pos_y=optional_decimal(
            coordinates.get("y0")
        ),
        release_pos_z=optional_decimal(
            coordinates.get("z0")
        ),
        plate_x=optional_decimal(
            coordinates.get("pX")
        ),
        plate_z=optional_decimal(
            coordinates.get("pZ")
        ),
        strike_zone_top=optional_decimal(
            pitch_data.get("strikeZoneTop")
        ),
        strike_zone_bottom=optional_decimal(
            pitch_data.get("strikeZoneBottom")
        ),
        pfx_x=optional_decimal(
            breaks.get("breakHorizontal")
        ),
        pfx_z=optional_decimal(
            breaks.get("breakVertical")
        ),
        launch_speed=optional_decimal(
            hit_data.get("launchSpeed")
        ),
        launch_angle=optional_decimal(
            hit_data.get("launchAngle")
        ),
        hit_distance=optional_decimal(
            hit_data.get("totalDistance")
        ),
        hit_location=optional_integer(
            hit_coordinates.get("coordX")
        ),
        trajectory=optional_text(
            hit_data.get("trajectory")
        ),
        hardness=optional_text(
            hit_data.get("hardness")
        ),
        estimated_batting_average=None,
        estimated_woba=None,
        estimated_slugging=None,
        zone=optional_integer(pitch_data.get("zone")),
        type_code=optional_text(call.get("code")),
        runner_on_first="1B" in runner_bases,
        runner_on_second="2B" in runner_bases,
        runner_on_third="3B" in runner_bases,
        home_score=optional_integer(
            result.get("homeScore")
        ),
        away_score=optional_integer(
            result.get("awayScore")
        ),
        raw_payload=raw_payload,
    )


def parse_feed_pitches(
    feed: dict[str, Any],
    game_pk: int,
    fallback_date: date,
) -> list[PitchRecord]:
    """Extract every pitch from one feed."""
    live_data = feed.get("liveData") or {}
    plays = live_data.get("plays") or {}
    all_plays = plays.get("allPlays") or []

    if not isinstance(all_plays, list):
        raise PitchValidationError(
            f"Game {game_pk} has no valid allPlays list."
        )

    game_date = extract_game_date(feed, fallback_date)
    records: list[PitchRecord] = []

    for at_bat in all_plays:
        if not isinstance(at_bat, dict):
            continue

        play_events = at_bat.get("playEvents") or []

        for play_event in play_events:
            if not isinstance(play_event, dict):
                continue

            if not play_event.get("isPitch", False):
                continue

            try:
                records.append(
                    parse_pitch(
                        game_pk=game_pk,
                        game_date=game_date,
                        at_bat=at_bat,
                        play_event=play_event,
                    )
                )
            except PitchValidationError as exc:
                LOGGER.warning(
                    "Skipping invalid pitch in game %s: %s",
                    game_pk,
                    exc,
                )

    return records


def upsert_pitches(
    session: Session,
    records: list[PitchRecord],
) -> tuple[int, int]:
    """Insert or update one game's pitches."""
    if not records:
        return 0, 0

    existing_count = session.scalar(
        select(func.count())
        .select_from(Pitch)
        .where(Pitch.game_pk == records[0].game_pk)
    ) or 0

    statement = insert(Pitch).values(
        [record.as_dict() for record in records]
    )

    excluded = statement.excluded

    statement = statement.on_conflict_do_update(
        constraint="uq_pitches_game_at_bat_pitch",
        set_={
            "game_date": excluded.game_date,
            "plate_appearance_number": (
                excluded.plate_appearance_number
            ),
            "inning": excluded.inning,
            "inning_half": excluded.inning_half,
            "outs": excluded.outs,
            "balls": excluded.balls,
            "strikes": excluded.strikes,
            "pitcher_id": excluded.pitcher_id,
            "batter_id": excluded.batter_id,
            "pitch_type": excluded.pitch_type,
            "pitch_name": excluded.pitch_name,
            "description": excluded.description,
            "event": excluded.event,
            "event_type": excluded.event_type,
            "is_ball": excluded.is_ball,
            "is_strike": excluded.is_strike,
            "is_in_play": excluded.is_in_play,
            "release_speed": excluded.release_speed,
            "effective_speed": excluded.effective_speed,
            "release_spin_rate": excluded.release_spin_rate,
            "release_extension": excluded.release_extension,
            "release_pos_x": excluded.release_pos_x,
            "release_pos_y": excluded.release_pos_y,
            "release_pos_z": excluded.release_pos_z,
            "plate_x": excluded.plate_x,
            "plate_z": excluded.plate_z,
            "strike_zone_top": excluded.strike_zone_top,
            "strike_zone_bottom": excluded.strike_zone_bottom,
            "pfx_x": excluded.pfx_x,
            "pfx_z": excluded.pfx_z,
            "launch_speed": excluded.launch_speed,
            "launch_angle": excluded.launch_angle,
            "hit_distance": excluded.hit_distance,
            "hit_location": excluded.hit_location,
            "trajectory": excluded.trajectory,
            "hardness": excluded.hardness,
            "zone": excluded.zone,
            "type_code": excluded.type_code,
            "runner_on_first": excluded.runner_on_first,
            "runner_on_second": excluded.runner_on_second,
            "runner_on_third": excluded.runner_on_third,
            "home_score": excluded.home_score,
            "away_score": excluded.away_score,
            "raw_payload": excluded.raw_payload,
        },
    )

    session.execute(statement)

    inserted = max(len(records) - existing_count, 0)
    updated = len(records) - inserted

    return inserted, updated


def select_games_for_collection(
    *,
    start_date: date,
    end_date: date,
    force: bool,
    limit: int | None,
) -> list[tuple[int, date]]:
    """Select completed games requiring pitch collection."""
    with session_scope() as session:
        statement = (
            select(Game.game_pk, Game.game_date)
            .where(Game.game_date.between(start_date, end_date))
            .where(
                Game.abstract_status == "Final"
            )
            .order_by(Game.game_date, Game.game_pk)
        )

        if not force:
            statement = statement.where(
                or_(
                    Game.pitches_collected.is_(False),
                    Game.pitch_count.is_(None),
                    Game.pitch_count == 0,
                )
            )

        if limit is not None:
            statement = statement.limit(limit)

        return list(session.execute(statement).all())


def collect_one_game(
    client: MLBAPIClient,
    game_pk: int,
    game_date: date,
    replace: bool = False,
) -> tuple[int, int]:
    """Collect and commit one game independently."""
    feed = fetch_game_feed(client, game_pk)
    records = parse_feed_pitches(feed, game_pk, game_date)

    if not records:
        raise RuntimeError(
            f"Game {game_pk} returned zero pitches; "
            "it will remain eligible for a later retry."
        )

    with session_scope() as session:
        game = session.get(Game, game_pk)

        if game is None:
            raise RuntimeError(
                f"Game {game_pk} does not exist locally."
            )

        for record in records:
            ensure_player(
                session,
                record.pitcher_id,
                extract_player_name(
                    feed,
                    record.pitcher_id,
                ),
            )
            ensure_player(
                session,
                record.batter_id,
                extract_player_name(
                    feed,
                    record.batter_id,
                ),
            )

        if replace:
            session.execute(
                delete(Pitch).where(
                    Pitch.game_pk == game_pk
                )
            )

        inserted, updated = upsert_pitches(
            session,
            records,
        )

        game.pitches_collected = True
        game.pitch_count = len(records)
        game.pitches_collected_at = datetime.now(timezone.utc)
        game.pitch_collection_error = None

    return inserted, updated


def collect_pitches(
    *,
    start_date: date,
    end_date: date,
    force: bool = False,
    replace: bool = False,
    limit: int | None = None,
) -> CollectionMetrics:
    """Collect pitches game by game."""
    if end_date < start_date:
        raise ValueError(
            "end_date cannot be earlier than start_date."
        )

    metrics = CollectionMetrics()
    collection_run_id: int | None = None

    games = select_games_for_collection(
        start_date=start_date,
        end_date=end_date,
        force=force,
        limit=limit,
    )

    with session_scope() as session:
        collection_run = start_collection_run(
            session=session,
            collector_name=COLLECTOR_NAME,
            requested_start_date=start_date,
            requested_end_date=end_date,
        )
        collection_run_id = collection_run.collection_run_id

    metrics.records_read = len(games)

    try:
        with MLBAPIClient() as client:
            for position, (game_pk, game_date) in enumerate(
                games,
                start=1,
            ):
                LOGGER.info(
                    "Collecting game %s (%s of %s)",
                    game_pk,
                    position,
                    len(games),
                )

                try:
                    inserted, updated = collect_one_game(
                        client=client,
                        game_pk=game_pk,
                        game_date=game_date,
                        replace=replace,
                    )

                    metrics.records_inserted += inserted
                    metrics.records_updated += updated

                except Exception as exc:
                    metrics.records_rejected += 1

                    LOGGER.exception(
                        "Game %s failed: %s",
                        game_pk,
                        exc,
                    )

                    with session_scope() as session:
                        game = session.get(Game, game_pk)

                        if game is not None:
                            game.pitch_collection_error = str(exc)[
                                :5000
                            ]

        with session_scope() as session:
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
                collection_run,
                metrics,
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
                        collection_run,
                        exc,
                        metrics,
                    )

        raise