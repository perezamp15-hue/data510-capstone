#!/usr/bin/env python3
"""
Refresh the MLB players dimension for every current MLB organization.

What it does
------------
1. Loads all MLB teams for the requested season.
2. Collects players from multiple roster types so injured, optioned, and
   recently moved players are less likely to be missed.
3. Hydrates each person record to obtain batting side and throwing hand.
4. Adds any batter_id or pitcher_id found in statcast_pitches but missing from
   the roster responses.
5. Upserts the results into public.players.
6. Prints a data-quality report for missing bats/throws values.

Run
---
python3 -m scripts.scrape_all_players --season 2026

Optional:
python3 -m scripts.scrape_all_players --season 2026 --sleep 0.08
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.sql.sqltypes import String
from sqlalchemy.engine import Engine

BASE_URL = "https://statsapi.mlb.com/api/v1"
ROSTER_TYPES = (
    "active",
    "40Man",
    "fullSeason",
    "depthChart",
)

PLAYER_COLUMN_CANDIDATES = {
    "player_id": ("player_id", "id", "mlb_id"),
    "full_name": ("full_name", "player_name", "name"),
    "first_name": ("first_name",),
    "last_name": ("last_name",),
    "bats": ("bats", "bat_side", "batter_side"),
    "throws": ("throws", "throw_side", "pitcher_throws"),
    "primary_position": ("primary_position", "position", "position_name"),
    "primary_position_code": ("primary_position_code", "position_code"),
    "current_team_id": ("current_team_id", "team_id"),
    "active": ("active", "is_active"),
}


@dataclass(frozen=True)
class Player:
    player_id: int
    full_name: str | None
    first_name: str | None
    last_name: str | None
    bats: str | None
    throws: str | None
    primary_position: str | None
    primary_position_code: str | None
    current_team_id: int | None
    active: bool | None


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing from the environment or .env file.")

    return create_engine(
        normalize_database_url(url),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 20},
    )


def get_json(session: requests.Session, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = session.get(f"{BASE_URL}{path}", params=params, timeout=40)
    response.raise_for_status()
    return response.json()


def current_teams(session: requests.Session, season: int) -> list[int]:
    payload = get_json(
        session,
        "/teams",
        {
            "sportId": 1,
            "season": season,
            "hydrate": "league,division",
        },
    )
    return sorted(
        {
            int(team["id"])
            for team in payload.get("teams", [])
            if team.get("id") is not None
        }
    )


def roster_player_ids(
    session: requests.Session,
    team_ids: Iterable[int],
    season: int,
    sleep_seconds: float,
) -> set[int]:
    ids: set[int] = set()

    for team_id in team_ids:
        for roster_type in ROSTER_TYPES:
            try:
                payload = get_json(
                    session,
                    f"/teams/{team_id}/roster",
                    {"rosterType": roster_type, "season": season},
                )
            except requests.HTTPError as exc:
                print(
                    f"WARNING team={team_id} roster={roster_type}: {exc}",
                    file=sys.stderr,
                )
                continue

            for row in payload.get("roster", []):
                person = row.get("person") or {}
                player_id = person.get("id")
                if player_id is not None:
                    ids.add(int(player_id))

            if sleep_seconds:
                time.sleep(sleep_seconds)

    return ids


def discover_pitch_source(engine: Engine) -> tuple[str, str] | None:
    """Find a table containing both batter_id and pitcher_id."""
    inspector = inspect(engine)
    preferred_names = (
        "statcast_pitches",
        "pitches",
        "pitch_by_pitch",
        "pitch_data",
        "game_pitches",
    )

    candidates: list[tuple[int, str, str]] = []
    for schema in inspector.get_schema_names():
        if schema in {"information_schema", "pg_catalog"}:
            continue
        for table_name in inspector.get_table_names(schema=schema):
            try:
                columns = {
                    column["name"]
                    for column in inspector.get_columns(table_name, schema=schema)
                }
            except Exception:
                continue

            if {"batter_id", "pitcher_id"}.issubset(columns):
                try:
                    priority = preferred_names.index(table_name)
                except ValueError:
                    priority = len(preferred_names)
                candidates.append((priority, schema, table_name))

    if not candidates:
        return None

    _, schema, table_name = sorted(candidates)[0]
    return schema, table_name


def warehouse_player_ids(engine: Engine) -> set[int]:
    """Include every player referenced by the warehouse pitch table."""
    source = discover_pitch_source(engine)
    if source is None:
        print(
            "WARNING: No table containing both batter_id and pitcher_id was found. "
            "Roster players will still be refreshed.",
            file=sys.stderr,
        )
        return set()

    schema, table_name = source
    print(f"Pitch source discovered: {schema}.{table_name}")

    # Identifiers are obtained from SQLAlchemy inspection, not user input.
    query = text(
        f"""
        SELECT DISTINCT player_id
        FROM (
            SELECT batter_id AS player_id
            FROM "{schema}"."{table_name}"
            WHERE batter_id IS NOT NULL

            UNION

            SELECT pitcher_id AS player_id
            FROM "{schema}"."{table_name}"
            WHERE pitcher_id IS NOT NULL
        ) AS referenced_players
        """
    )

    try:
        with engine.connect() as connection:
            return {int(row[0]) for row in connection.execute(query)}
    except Exception as exc:
        print(
            "WARNING: Could not read player IDs from "
            f"{schema}.{table_name}. Roster players will still be refreshed. "
            f"Reason: {exc}",
            file=sys.stderr,
        )
        return set()


def chunked(values: list[int], size: int) -> Iterable[list[int]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def hydrate_players(
    session: requests.Session,
    player_ids: set[int],
    sleep_seconds: float,
) -> list[Player]:
    players: dict[int, Player] = {}

    # The people endpoint accepts comma-separated IDs. Small batches are safer.
    for batch in chunked(sorted(player_ids), 75):
        payload = get_json(
            session,
            "/people",
            {
                "personIds": ",".join(str(value) for value in batch),
                "hydrate": "currentTeam,team,stats(group=[hitting,pitching],type=[yearByYear])",
            },
        )

        for person in payload.get("people", []):
            player_id = person.get("id")
            if player_id is None:
                continue

            bat_side = (person.get("batSide") or {}).get("code")
            pitch_hand = (person.get("pitchHand") or {}).get("code")
            position = person.get("primaryPosition") or {}
            team = person.get("currentTeam") or {}

            players[int(player_id)] = Player(
                player_id=int(player_id),
                full_name=person.get("fullName"),
                first_name=person.get("firstName"),
                last_name=person.get("lastName"),
                bats=bat_side if bat_side in {"L", "R", "S"} else None,
                throws=pitch_hand if pitch_hand in {"L", "R", "S"} else None,
                primary_position=position.get("name"),
                primary_position_code=position.get("code"),
                current_team_id=int(team["id"]) if team.get("id") is not None else None,
                active=person.get("active"),
            )

        if sleep_seconds:
            time.sleep(sleep_seconds)

    return list(players.values())


def table_columns(engine: Engine) -> set[str]:
    inspector = inspect(engine)
    return {
        column["name"]
        for column in inspector.get_columns("players", schema="public")
    }


def resolve_columns(existing: set[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for logical_name, candidates in PLAYER_COLUMN_CANDIDATES.items():
        match = next((candidate for candidate in candidates if candidate in existing), None)
        if match:
            resolved[logical_name] = match

    if "player_id" not in resolved:
        raise RuntimeError(
            "public.players does not have a recognized player ID column. "
            "Expected one of: player_id, id, mlb_id."
        )
    return resolved


def valid_team_ids(engine: Engine) -> set[int]:
    """Return team IDs accepted by the players.current_team_id foreign key."""
    inspector = inspect(engine)
    if "teams" not in inspector.get_table_names(schema="public"):
        return set()

    columns = {
        column["name"]
        for column in inspector.get_columns("teams", schema="public")
    }
    team_id_column = next(
        (name for name in ("team_id", "id", "mlb_team_id") if name in columns),
        None,
    )
    if team_id_column is None:
        return set()

    with engine.connect() as connection:
        rows = connection.execute(
            text(f'SELECT "{team_id_column}" FROM public.teams')
        )
        return {int(row[0]) for row in rows if row[0] is not None}


def sanitize_team_references(engine: Engine, players: list[Player]) -> list[Player]:
    """
    Keep only current_team_id values present in public.teams.

    MLB's people endpoint can return minor-league, spring, international,
    inactive, or historical organization IDs. Those values cannot be inserted
    when players.current_team_id references the MLB-only teams table.
    """
    accepted = valid_team_ids(engine)
    if not accepted:
        print(
            "WARNING: Could not identify accepted team IDs. "
            "All current_team_id values will be stored as NULL.",
            file=sys.stderr,
        )

    cleaned: list[Player] = []
    cleared = 0

    for player in players:
        team_id = player.current_team_id
        if team_id is not None and team_id not in accepted:
            team_id = None
            cleared += 1

        cleaned.append(
            Player(
                player_id=player.player_id,
                full_name=player.full_name,
                first_name=player.first_name,
                last_name=player.last_name,
                bats=player.bats,
                throws=player.throws,
                primary_position=player.primary_position,
                primary_position_code=player.primary_position_code,
                current_team_id=team_id,
                active=player.active,
            )
        )

    print(f"Invalid/non-MLB team references cleared: {cleared:,}")
    return cleaned


def string_column_limits(engine: Engine) -> dict[str, int]:
    """Return character limits for bounded text columns in public.players."""
    limits: dict[str, int] = {}
    inspector = inspect(engine)

    for column in inspector.get_columns("players", schema="public"):
        column_type = column.get("type")
        length = getattr(column_type, "length", None)
        if isinstance(length, int) and length > 0:
            limits[column["name"]] = length

    return limits


def fit_record_to_schema(
    record: dict[str, Any],
    logical_fields: list[str],
    columns: dict[str, str],
    limits: dict[str, int],
) -> dict[str, Any]:
    """
    Fit outgoing string values to the actual database column widths.

    Batting side and throwing hand are already one-character codes. For a
    bounded position column, prefer MLB's compact position code when the full
    position name is too long. Other bounded strings are safely truncated.
    """
    fitted = dict(record)

    for logical_name in logical_fields:
        physical_name = columns[logical_name]
        limit = limits.get(physical_name)
        value = fitted.get(logical_name)

        if limit is None or value is None or not isinstance(value, str):
            continue

        if len(value) <= limit:
            continue

        if logical_name == "primary_position":
            compact_code = fitted.get("primary_position_code")
            if isinstance(compact_code, str) and compact_code:
                fitted[logical_name] = compact_code[:limit]
            else:
                fitted[logical_name] = value[:limit]
        else:
            fitted[logical_name] = value[:limit]

    return fitted


def upsert_players(engine: Engine, players: list[Player]) -> None:
    existing = table_columns(engine)
    columns = resolve_columns(existing)

    logical_fields = [
        "player_id",
        "full_name",
        "first_name",
        "last_name",
        "bats",
        "throws",
        "primary_position",
        "primary_position_code",
        "current_team_id",
        "active",
    ]
    logical_fields = [field for field in logical_fields if field in columns]

    physical_columns = [columns[field] for field in logical_fields]
    insert_columns = ", ".join(physical_columns)
    insert_values = ", ".join(f":{field}" for field in logical_fields)

    id_column = columns["player_id"]
    update_fields = [field for field in logical_fields if field != "player_id"]
    update_clause = ", ".join(
        f"{columns[field]} = EXCLUDED.{columns[field]}"
        for field in update_fields
    )

    sql = text(
        f"""
        INSERT INTO public.players ({insert_columns})
        VALUES ({insert_values})
        ON CONFLICT ({id_column}) DO UPDATE SET
            {update_clause}
        """
    )

    limits = string_column_limits(engine)

    raw_records = [
        {field: getattr(player, field) for field in logical_fields}
        for player in players
    ]
    records = [
        fit_record_to_schema(record, logical_fields, columns, limits)
        for record in raw_records
    ]

    if limits:
        print(
            "Bounded player text columns: "
            + ", ".join(
                f"{column}={length}"
                for column, length in sorted(limits.items())
            )
        )

    batch_size = 250
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        try:
            with engine.begin() as connection:
                connection.execute(sql, batch)
        except Exception:
            # Retry individually so a future schema-specific bad record is
            # reported precisely instead of hiding inside a 250-row batch.
            for record in batch:
                try:
                    with engine.begin() as connection:
                        connection.execute(sql, record)
                except Exception as exc:
                    raise RuntimeError(
                        "Player upsert failed after schema fitting. "
                        f"player_id={record.get('player_id')}, "
                        f"name={record.get('full_name')!r}, "
                        f"record={record!r}"
                    ) from exc


def print_quality_report(engine: Engine) -> None:
    existing = table_columns(engine)
    columns = resolve_columns(existing)

    player_id = columns["player_id"]
    bats = columns.get("bats")
    throws = columns.get("throws")
    full_name = columns.get("full_name")

    display_name = full_name or f"CAST({player_id} AS text)"

    with engine.connect() as connection:
        total = connection.execute(
            text("SELECT COUNT(*) FROM public.players")
        ).scalar_one()

        print(f"\nPlayers currently stored: {total:,}")

        if bats:
            missing_bats = connection.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM public.players
                    WHERE {bats} IS NULL OR TRIM(CAST({bats} AS text)) = ''
                    """
                )
            ).scalar_one()
            print(f"Missing batting side: {missing_bats:,}")

        if throws:
            missing_throws = connection.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM public.players
                    WHERE {throws} IS NULL OR TRIM(CAST({throws} AS text)) = ''
                    """
                )
            ).scalar_one()
            print(f"Missing throwing hand: {missing_throws:,}")

        if bats or throws:
            predicates = []
            if bats:
                predicates.append(f"({bats} IS NULL OR TRIM(CAST({bats} AS text)) = '')")
            if throws:
                predicates.append(f"({throws} IS NULL OR TRIM(CAST({throws} AS text)) = '')")

            rows = connection.execute(
                text(
                    f"""
                    SELECT {player_id}, {display_name}
                    FROM public.players
                    WHERE {" OR ".join(predicates)}
                    ORDER BY {display_name}
                    LIMIT 30
                    """
                )
            ).fetchall()

            if rows:
                print("\nFirst players still missing handedness:")
                for row in rows:
                    print(f"  {row[0]} | {row[1]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.05,
        help="Pause between MLB API requests.",
    )
    args = parser.parse_args()

    engine = get_engine()

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    print("Database connection: OK")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "data510-capstone-player-refresh/1.0",
            "Accept": "application/json",
        }
    )

    teams = current_teams(session, args.season)
    print(f"MLB teams found: {len(teams)}")

    roster_ids = roster_player_ids(session, teams, args.season, args.sleep)
    warehouse_ids = warehouse_player_ids(engine)
    all_ids = roster_ids | warehouse_ids

    print(f"Roster player IDs: {len(roster_ids):,}")
    print(f"Warehouse-referenced IDs: {len(warehouse_ids):,}")
    print(f"Unique players to hydrate: {len(all_ids):,}")

    players = hydrate_players(session, all_ids, args.sleep)
    print(f"Player records returned by MLB: {len(players):,}")

    if not players:
        raise RuntimeError("No player records were returned; database was not changed.")

    players = sanitize_team_references(engine, players)
    upsert_players(engine, players)
    print(f"Upserted players: {len(players):,}")

    print_quality_report(engine)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
