"""Restartable and concurrent MLB pitch-by-pitch collector."""

from __future__ import annotations

import json
import logging
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass, fields
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, func, select
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
MAX_WORKERS = 8


class PitchValidationError(ValueError):
    """Raised when a pitch event cannot be validated."""


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
        """Return values compatible with SQLAlchemy inserts."""
        return {
            field.name: getattr(self, field.name)
            for field in fields(self)
        }


@dataclass(frozen=True, slots=True)
class GameCollectionResult:
    """Result returned by one concurrent game worker."""

    game_pk: int
    pitch_count: int
    inserted: int
    updated: int


def optional_text(value: Any) -> str | None:
    """Normalize optional text."""
    if value is None:
        return None

    result = str(value).strip()
    return result or None


def optional_integer(value: Any) -> int | None:
    """Convert an optional value to an integer."""
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_decimal(value: Any) -> Decimal | None:
    """Convert an optional value to Decimal."""
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
    """Fetch one MLB game live-feed payload."""
    return client.get_json(
        f"/v1.1/game/{game_pk}/feed/live"
    )


def extract_game_date(
    feed: dict[str, Any],
    fallback_date: date,
) -> date:
    """Extract the official date from a live feed."""
    game_data = feed.get("gameData") or {}
    datetime_data = game_data.get("datetime") or {}

    official_date = optional_text(
        datetime_data.get("officialDate")
    )

    if official_date:
        try:
            return date.fromisoformat(official_date[:10])
        except ValueError:
            LOGGER.warning(
                "Could not parse official date %r.",
                official_date,
            )

    return fallback_date


def extract_player_name(
    feed: dict[str, Any],
    player_id: int,
) -> str:
    """Get a player name from the game feed."""
    game_data = feed.get("gameData") or {}
    players = game_data.get("players") or {}
    player = players.get(f"ID{player_id}") or {}

    return (
        optional_text(player.get("fullName"))
        or f"MLB Player {player_id}"
    )


def extract_player_attribute(
    feed: dict[str, Any],
    player_id: int,
    key: str,
) -> str | None:
    """Read an optional player attribute from the feed."""
    game_data = feed.get("gameData") or {}
    players = game_data.get("players") or {}
    player = players.get(f"ID{player_id}") or {}

    value = player.get(key)

    if isinstance(value, dict):
        return optional_text(value.get("code"))

    return optional_text(value)


def ensure_player(
    session: Session,
    feed: dict[str, Any],
    player_id: int,
) -> None:
    """Insert a minimal player row when missing."""
    statement = insert(Player).values(
        player_id=player_id,
        full_name=extract_player_name(
            feed,
            player_id,
        ),
        bats=extract_player_attribute(
            feed,
            player_id,
            "batSide",
        ),
        throws=extract_player_attribute(
            feed,
            player_id,
            "pitchHand",
        ),
        active=True,
    )

    statement = statement.on_conflict_do_nothing(
        index_elements=[Player.player_id]
    )

    session.execute(statement)


def parse_runner_state(
    at_bat: dict[str, Any],
) -> tuple[bool, bool, bool]:
    """Estimate occupied bases from runner movements."""
    runners = at_bat.get("runners") or []

    occupied_bases: set[str] = set()

    for runner in runners:
        if not isinstance(runner, dict):
            continue

        movement = runner.get("movement") or {}
        start_base = optional_text(movement.get("start"))

        if start_base:
            occupied_bases.add(start_base)

    return (
        "1B" in occupied_bases,
        "2B" in occupied_bases,
        "3B" in occupied_bases,
    )


def parse_pitch(
    *,
    game_pk: int,
    game_date: date,
    at_bat: dict[str, Any],
    play_event: dict[str, Any],
    store_raw_payload: bool,
) -> PitchRecord:
    """Parse one pitch event."""
    about = at_bat.get("about") or {}
    matchup = at_bat.get("matchup") or {}
    result = at_bat.get("result") or {}

    count = play_event.get("count") or {}
    details = play_event.get("details") or {}

    pitch_data = play_event.get("pitchData") or {}
    coordinates = pitch_data.get("coordinates") or {}
    breaks = pitch_data.get("breaks") or {}

    hit_data = play_event.get("hitData") or {}

    at_bat_number = optional_integer(
        about.get("atBatIndex")
    )

    pitch_number = optional_integer(
        play_event.get("pitchNumber")
    )

    pitcher = matchup.get("pitcher") or {}
    batter = matchup.get("batter") or {}

    pitcher_id = pitcher.get("id")
    batter_id = batter.get("id")

    if at_bat_number is None:
        raise PitchValidationError(
            "Pitch is missing atBatIndex."
        )

    if pitch_number is None:
        raise PitchValidationError(
            f"At-bat {at_bat_number} has no pitch number."
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

    (
        runner_on_first,
        runner_on_second,
        runner_on_third,
    ) = parse_runner_state(at_bat)

    raw_payload = None

    if store_raw_payload:
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
        inning_half=optional_text(
            about.get("halfInning")
        ),
        outs=optional_integer(count.get("outs")),

        balls=optional_integer(count.get("balls")),
        strikes=optional_integer(count.get("strikes")),

        pitcher_id=pitcher_id,
        batter_id=batter_id,

        pitch_type=optional_text(
            pitch_type.get("code")
        ),
        pitch_name=optional_text(
            pitch_type.get("description")
        ),
        description=optional_text(
            details.get("description")
        ),
        event=optional_text(result.get("event")),
        event_type=optional_text(
            result.get("eventType")
        ),

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
            hit_data.get("location")
        ),
        trajectory=optional_text(
            hit_data.get("trajectory")
        ),
        hardness=optional_text(
            hit_data.get("hardness")
        ),

        estimated_batting_average=optional_decimal(
            hit_data.get("estimatedBattingAverage")
        ),
        estimated_woba=optional_decimal(
            hit_data.get("estimatedWoba")
        ),
        estimated_slugging=optional_decimal(
            hit_data.get("estimatedSlugging")
        ),

        zone=optional_integer(pitch_data.get("zone")),
        type_code=optional_text(call.get("code")),

        runner_on_first=runner_on_first,
        runner_on_second=runner_on_second,
        runner_on_third=runner_on_third,

        home_score=optional_integer(
            result.get("homeScore")
        ),
        away_score=optional_integer(
            result.get("awayScore")
        ),

        raw_payload=raw_payload,
    )


def parse_feed_pitches(
    *,
    feed: dict[str, Any],
    game_pk: int,
    fallback_date: date,
    store_raw_payload: bool,
) -> list[PitchRecord]:
    """Extract every valid pitch from one game feed."""
    live_data = feed.get("liveData") or {}
    plays = live_data.get("plays") or {}
    all_plays = plays.get("allPlays") or []

    if not isinstance(all_plays, list):
        raise PitchValidationError(
            f"Game {game_pk} has no valid allPlays list."
        )

    official_game_date = extract_game_date(
        feed,
        fallback_date,
    )

    records: list[PitchRecord] = []

    for at_bat in all_plays:
        if not isinstance(at_bat, dict):
            continue

        play_events = at_bat.get("playEvents") or []

        for play_event in play_events:
            if not isinstance(play_event, dict):
                continue

            is_pitch = play_event.get("isPitch")

            if (
                is_pitch is not True
                and "pitchData" not in play_event
            ):
                continue

            try:
                record = parse_pitch(
                    game_pk=game_pk,
                    game_date=official_game_date,
                    at_bat=at_bat,
                    play_event=play_event,
                    store_raw_payload=store_raw_payload,
                )
            except PitchValidationError as exc:
                LOGGER.warning(
                    "Skipping invalid pitch in game %s: %s",
                    game_pk,
                    exc,
                )
                continue

            records.append(record)

    return records


def deduplicate_pitch_records(
    records: list[PitchRecord],
) -> list[PitchRecord]:
    """Keep one row per game, at-bat, and pitch number."""
    by_key: dict[
        tuple[int, int, int],
        PitchRecord,
    ] = {}

    for record in records:
        key = (
            record.game_pk,
            record.at_bat_number,
            record.pitch_number,
        )

        by_key[key] = record

    return list(by_key.values())


def upsert_pitches(
    session: Session,
    records: list[PitchRecord],
) -> tuple[int, int]:
    """Insert or update one game's pitches."""
    records = deduplicate_pitch_records(records)

    if not records:
        return 0, 0

    game_pk = records[0].game_pk

    existing_keys = set(
        session.execute(
            select(
                Pitch.at_bat_number,
                Pitch.pitch_number,
            )
            .where(Pitch.game_pk == game_pk)
        ).all()
    )

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
            "is_pitch": excluded.is_pitch,
            "is_ball": excluded.is_ball,
            "is_strike": excluded.is_strike,
            "is_in_play": excluded.is_in_play,
            "release_speed": excluded.release_speed,
            "effective_speed": excluded.effective_speed,
            "release_spin_rate": (
                excluded.release_spin_rate
            ),
            "release_extension": (
                excluded.release_extension
            ),
            "release_pos_x": excluded.release_pos_x,
            "release_pos_y": excluded.release_pos_y,
            "release_pos_z": excluded.release_pos_z,
            "plate_x": excluded.plate_x,
            "plate_z": excluded.plate_z,
            "strike_zone_top": (
                excluded.strike_zone_top
            ),
            "strike_zone_bottom": (
                excluded.strike_zone_bottom
            ),
            "pfx_x": excluded.pfx_x,
            "pfx_z": excluded.pfx_z,
            "launch_speed": excluded.launch_speed,
            "launch_angle": excluded.launch_angle,
            "hit_distance": excluded.hit_distance,
            "hit_location": excluded.hit_location,
            "trajectory": excluded.trajectory,
            "hardness": excluded.hardness,
            "estimated_batting_average": (
                excluded.estimated_batting_average
            ),
            "estimated_woba": excluded.estimated_woba,
            "estimated_slugging": (
                excluded.estimated_slugging
            ),
            "zone": excluded.zone,
            "type_code": excluded.type_code,
            "runner_on_first": (
                excluded.runner_on_first
            ),
            "runner_on_second": (
                excluded.runner_on_second
            ),
            "runner_on_third": (
                excluded.runner_on_third
            ),
            "home_score": excluded.home_score,
            "away_score": excluded.away_score,
            "raw_payload": excluded.raw_payload,
        },
    )

    session.execute(statement)

    inserted = sum(
        (
            record.at_bat_number,
            record.pitch_number,
        )
        not in existing_keys
        for record in records
    )

    updated = len(records) - inserted

    return inserted, updated


def select_games_for_collection(
    *,
    start_date: date,
    end_date: date,
    force: bool,
    limit: int | None,
) -> list[tuple[int, date]]:
    """Select eligible games for pitch collection."""
    with session_scope() as session:
        statement = (
            select(
                Game.game_pk,
                Game.game_date,
            )
            .where(
                Game.game_date.between(
                    start_date,
                    end_date,
                )
            )
            .where(
                Game.abstract_status.in_(
                    ["Final", "Live"]
                )
                | Game.detailed_status.in_(
                    [
                        "Final",
                        "Game Over",
                        "Completed Early",
                        "In Progress",
                    ]
                )
            )
            .order_by(
                Game.game_date,
                Game.game_pk,
            )
        )

        if not force:
            statement = statement.where(
                Game.pitches_collected.is_(False)
            )

        if limit is not None:
            statement = statement.limit(limit)

        rows = session.execute(statement).all()

    return [
        (int(row.game_pk), row.game_date)
        for row in rows
    ]


def record_game_error(
    game_pk: int,
    error: Exception,
) -> None:
    """Store an error for one failed game."""
    try:
        with session_scope() as session:
            game = session.get(Game, game_pk)

            if game is not None:
                game.pitches_collected = False
                game.pitch_collection_error = str(error)[
                    :5000
                ]

    except Exception:
        LOGGER.exception(
            "Could not record collection error for game %s.",
            game_pk,
        )


def collect_one_game(
    *,
    client: MLBAPIClient,
    game_pk: int,
    game_date: date,
    replace: bool,
    store_raw_payload: bool,
) -> GameCollectionResult:
    """Collect and commit one game independently."""
    feed = fetch_game_feed(
        client,
        game_pk,
    )

    records = parse_feed_pitches(
        feed=feed,
        game_pk=game_pk,
        fallback_date=game_date,
        store_raw_payload=store_raw_payload,
    )

    if not records:
        raise RuntimeError(
            f"Game {game_pk} returned zero parsed pitches."
        )

    player_ids = {
        record.pitcher_id
        for record in records
    } | {
        record.batter_id
        for record in records
    }

    with session_scope() as session:
        game = session.get(Game, game_pk)

        if game is None:
            raise RuntimeError(
                f"Game {game_pk} does not exist locally."
            )

        for player_id in player_ids:
            ensure_player(
                session=session,
                feed=feed,
                player_id=player_id,
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
        game.pitches_collected_at = datetime.now(
            timezone.utc
        )
        game.pitch_collection_error = None

    return GameCollectionResult(
        game_pk=game_pk,
        pitch_count=len(records),
        inserted=inserted,
        updated=updated,
    )


def collect_game_worker(
    *,
    game_pk: int,
    game_date: date,
    replace: bool,
    store_raw_payload: bool,
) -> GameCollectionResult:
    """Collect one game in a thread-safe worker."""
    with MLBAPIClient() as client:
        return collect_one_game(
            client=client,
            game_pk=game_pk,
            game_date=game_date,
            replace=replace,
            store_raw_payload=store_raw_payload,
        )


def collect_games_sequentially(
    *,
    games: list[tuple[int, date]],
    replace: bool,
    store_raw_payload: bool,
    metrics: CollectionMetrics,
) -> None:
    """Collect games with a shared HTTP client."""
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
                result = collect_one_game(
                    client=client,
                    game_pk=game_pk,
                    game_date=game_date,
                    replace=replace,
                    store_raw_payload=store_raw_payload,
                )
            except Exception as exc:
                metrics.records_rejected += 1

                LOGGER.exception(
                    "Game %s failed: %s",
                    game_pk,
                    exc,
                )

                record_game_error(
                    game_pk,
                    exc,
                )

                continue

            metrics.records_inserted += result.inserted
            metrics.records_updated += result.updated

            LOGGER.info(
                "Completed game %s: pitches=%s "
                "inserted=%s updated=%s",
                result.game_pk,
                result.pitch_count,
                result.inserted,
                result.updated,
            )


def collect_games_concurrently(
    *,
    games: list[tuple[int, date]],
    replace: bool,
    store_raw_payload: bool,
    workers: int,
    metrics: CollectionMetrics,
) -> None:
    """Collect multiple games concurrently."""
    future_to_game: dict[
        Future[GameCollectionResult],
        int,
    ] = {}

    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="pitch-backfill",
    ) as executor:
        for game_pk, game_date in games:
            future = executor.submit(
                collect_game_worker,
                game_pk=game_pk,
                game_date=game_date,
                replace=replace,
                store_raw_payload=store_raw_payload,
            )

            future_to_game[future] = game_pk

        for completed_count, future in enumerate(
            as_completed(future_to_game),
            start=1,
        ):
            game_pk = future_to_game[future]

            try:
                result = future.result()
            except Exception as exc:
                metrics.records_rejected += 1

                LOGGER.exception(
                    "Game %s failed: %s",
                    game_pk,
                    exc,
                )

                record_game_error(
                    game_pk,
                    exc,
                )

                continue

            metrics.records_inserted += result.inserted
            metrics.records_updated += result.updated

            LOGGER.info(
                "Completed game %s (%s of %s): "
                "pitches=%s inserted=%s updated=%s",
                result.game_pk,
                completed_count,
                len(games),
                result.pitch_count,
                result.inserted,
                result.updated,
            )


def collect_pitches(
    *,
    start_date: date,
    end_date: date,
    force: bool = False,
    replace: bool = False,
    limit: int | None = None,
    workers: int = 1,
    store_raw_payload: bool = False,
) -> CollectionMetrics:
    """Collect pitches game-by-game with optional concurrency."""
    if end_date < start_date:
        raise ValueError(
            "end_date cannot be earlier than start_date."
        )

    if workers < 1:
        raise ValueError(
            "workers must be at least 1."
        )

    if workers > MAX_WORKERS:
        raise ValueError(
            f"workers cannot exceed {MAX_WORKERS}."
        )

    if limit is not None and limit < 1:
        raise ValueError(
            "limit must be at least 1."
        )

    metrics = CollectionMetrics()
    collection_run_id: int | None = None

    games = select_games_for_collection(
        start_date=start_date,
        end_date=end_date,
        force=force,
        limit=limit,
    )

    metrics.records_read = len(games)

    with session_scope() as session:
        collection_run = start_collection_run(
            session=session,
            collector_name=COLLECTOR_NAME,
            requested_start_date=start_date,
            requested_end_date=end_date,
        )

        collection_run_id = (
            collection_run.collection_run_id
        )

    LOGGER.info(
        "Selected %s games from %s through %s "
        "using %s worker(s).",
        len(games),
        start_date,
        end_date,
        workers,
    )

    try:
        if not games:
            LOGGER.info(
                "No eligible games require pitch collection."
            )

        elif workers == 1:
            collect_games_sequentially(
                games=games,
                replace=replace,
                store_raw_payload=store_raw_payload,
                metrics=metrics,
            )

        else:
            collect_games_concurrently(
                games=games,
                replace=replace,
                store_raw_payload=store_raw_payload,
                workers=workers,
                metrics=metrics,
            )

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
                collection_run=collection_run,
                metrics=metrics,
            )

        LOGGER.info(
            "Pitch collection completed: "
            "games=%s inserted=%s updated=%s failed=%s",
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