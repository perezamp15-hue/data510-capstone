from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Sequence

import pandas as pd
from sqlalchemy import bindparam, text

from db_client import get_engine


@dataclass(frozen=True)
class HistoryFilters:
    season: int | None = None
    start_date: date | datetime | str | None = None
    end_date: date | datetime | str | None = None


PITCH_COLUMNS = """
    sp.pitch_id,
    sp.game_pk,
    sp.game_date,
    sp.pitcher_id,
    sp.batter_id,
    sp.at_bat_number,
    sp.plate_appearance_number,
    sp.pitch_number,
    sp.inning,
    sp.inning_half,
    sp.outs,
    sp.ball_count,
    sp.strike_count,
    sp.pitch_type,
    sp.pitch_description,
    sp.release_velocity,
    sp.release_spin_rate,
    sp.release_extension,
    sp.release_pos_x,
    sp.release_pos_y,
    sp.release_pos_z,
    sp.vx0,
    sp.vy0,
    sp.vz0,
    sp.ax,
    sp.ay,
    sp.az,
    sp.plate_crossing_x AS plate_x,
    sp.plate_crossing_z AS plate_z,
    sp.sz_top,
    sp.sz_bot AS sz_bottom,
    sp.runner_on_first,
    sp.runner_on_second,
    sp.runner_on_third,
    sp.home_score,
    sp.away_score,
    sp.play_event AS events,
    sp.exit_velocity,
    sp.launch_angle,
    sp.hit_distance,
    sp.spray_angle,
    sp.hit_location_x,
    sp.hit_location_y,
    sp.expected_woba,
    sp.expected_slugging,
    sp.is_hard_hit AS database_is_hard_hit,
    sp.is_sweet_spot AS database_is_sweet_spot
"""


class GamePlanRepository:
    """Database access for pitcher-versus-lineup game plans.

    Optional filters are appended only when supplied. This avoids psycopg's
    ambiguous NULL parameter error for optional season/date parameters.
    """

    @staticmethod
    def _append_history_filters(
        query: str,
        params: dict[str, Any],
        filters: HistoryFilters,
        table_alias: str = "sp",
    ) -> tuple[str, dict[str, Any]]:
        if filters.season is not None:
            query += f"\n  AND EXTRACT(YEAR FROM {table_alias}.game_date) = :season"
            params["season"] = int(filters.season)
        if filters.start_date is not None:
            query += f"\n  AND {table_alias}.game_date >= CAST(:start_date AS date)"
            params["start_date"] = filters.start_date
        if filters.end_date is not None:
            query += f"\n  AND {table_alias}.game_date <= CAST(:end_date AS date)"
            params["end_date"] = filters.end_date
        return query, params

    def get_game_context(self, game_pk: int) -> dict[str, Any]:
        query = text("""
        SELECT
            g.game_pk,
            g.game_date,
            g.season,
            g.scheduled_start,
            g.park_id,
            p.park_name,
            p.elevation AS park_elevation,
            g.home_team_id,
            ht.team_name AS home_team_name,
            ht.abbreviation AS home_team_abbreviation,
            g.away_team_id,
            at.team_name AS away_team_name,
            at.abbreviation AS away_team_abbreviation,
            g.day_night_type,
            g.temperature_f,
            g.sky_condition,
            g.wind_speed_mph,
            g.wind_direction
        FROM public.games AS g
        LEFT JOIN public.parks AS p ON p.park_id = g.park_id
        LEFT JOIN public.teams AS ht ON ht.team_id = g.home_team_id
        LEFT JOIN public.teams AS at ON at.team_id = g.away_team_id
        WHERE g.game_pk = :game_pk
        LIMIT 1
        """)
        with get_engine().connect() as connection:
            row = connection.execute(query, {"game_pk": int(game_pk)}).mappings().first()
        if not row:
            raise RuntimeError(f"No game was found for game_pk={game_pk}.")
        return dict(row)

    def get_lineup(self, game_pk: int, team_id: int) -> pd.DataFrame:
        query = text("""
        SELECT
            sl.game_pk,
            sl.team_id,
            t.team_name,
            t.abbreviation AS team_abbreviation,
            sl.batting_order_slot,
            sl.player_id,
            p.full_name AS batter_name,
            COALESCE(sl.batting_side, p.bats) AS bats,
            sl.field_position,
            p.position_code
        FROM public.starting_lineups AS sl
        LEFT JOIN public.players AS p ON p.player_id = sl.player_id
        LEFT JOIN public.teams AS t ON t.team_id = sl.team_id
        WHERE sl.game_pk = :game_pk
          AND sl.team_id = :team_id
        ORDER BY sl.batting_order_slot
        """)
        with get_engine().connect() as connection:
            frame = pd.read_sql(
                query,
                connection,
                params={"game_pk": int(game_pk), "team_id": int(team_id)},
            )
        if frame.empty:
            raise RuntimeError(
                f"No starting lineup was found for game_pk={game_pk}, team_id={team_id}."
            )
        return frame


    def get_manual_lineup(self, player_ids: Sequence[int], team_id: int | None = None) -> pd.DataFrame:
        cleaned = [int(v) for v in player_ids]
        if not cleaned:
            raise ValueError("At least one batter ID is required.")
        query = text("""
        SELECT p.player_id, p.full_name AS batter_name, p.bats, p.position_code,
               p.current_team_id AS actual_team_id,
               t.team_name AS actual_team_name,
               t.abbreviation AS actual_team_abbreviation
        FROM public.players p
        LEFT JOIN public.teams t ON t.team_id = p.current_team_id
        WHERE p.player_id IN :player_ids
        """).bindparams(bindparam("player_ids", expanding=True))
        with get_engine().connect() as connection:
            frame = pd.read_sql(query, connection, params={"player_ids": cleaned})
        lookup = {int(row.player_id): row._asdict() for row in frame.itertuples(index=False)}
        rows = []
        for slot, player_id in enumerate(cleaned, start=1):
            row = lookup.get(player_id, {})
            rows.append({
                "batting_order_slot": slot, "player_id": player_id,
                "batter_name": row.get("batter_name") or f"Batter {player_id}",
                "bats": row.get("bats") or "", "field_position": row.get("position_code") or "",
                "position_code": row.get("position_code") or "",
                "team_id": team_id or row.get("actual_team_id"),
                "team_name": self.get_team_metadata(team_id).get("team_name", "") if team_id else row.get("actual_team_name") or "",
                "team_abbreviation": self.get_team_metadata(team_id).get("abbreviation", "") if team_id else row.get("actual_team_abbreviation") or "",
                "actual_team_id": row.get("actual_team_id"),
                "actual_team_name": row.get("actual_team_name") or "",
            })
        return pd.DataFrame(rows)

    def get_team_metadata(self, team_id: int) -> dict[str, Any]:
        query = text("SELECT team_id, team_name, abbreviation FROM public.teams WHERE team_id=:team_id LIMIT 1")
        with get_engine().connect() as connection:
            row = connection.execute(query, {"team_id": int(team_id)}).mappings().first()
        return dict(row) if row else {"team_id": int(team_id), "team_name": f"Team {team_id}", "abbreviation": ""}

    def get_park_metadata(self, park_id: int) -> dict[str, Any]:
        query = text("SELECT park_id, park_name, elevation AS park_elevation FROM public.parks WHERE park_id=:park_id LIMIT 1")
        with get_engine().connect() as connection:
            row = connection.execute(query, {"park_id": int(park_id)}).mappings().first()
        return dict(row) if row else {"park_id": int(park_id), "park_name": f"Park {park_id}"}

    def find_team_by_name(self, team_name: str) -> dict[str, Any]:
        """Resolve a team from a full name, abbreviation, city, or common nickname."""
        cleaned = str(team_name).strip()
        if not cleaned:
            raise ValueError("A team name is required.")
        query = text("""
        SELECT team_id, team_name, abbreviation
        FROM public.teams
        WHERE LOWER(team_name) = LOWER(:value)
           OR LOWER(abbreviation) = LOWER(:value)
           OR LOWER(team_name) LIKE LOWER(:contains)
        ORDER BY
            CASE
                WHEN LOWER(team_name) = LOWER(:value) THEN 0
                WHEN LOWER(abbreviation) = LOWER(:value) THEN 1
                ELSE 2
            END,
            team_name
        LIMIT 2
        """)
        with get_engine().connect() as connection:
            rows = connection.execute(
                query,
                {"value": cleaned, "contains": f"%{cleaned}%"},
            ).mappings().all()
        if not rows:
            raise ValueError(f"No team was found matching {team_name!r}.")
        if len(rows) > 1 and rows[0]["team_name"] != rows[1]["team_name"]:
            choices = ", ".join(str(row["team_name"]) for row in rows)
            raise ValueError(f"Team name {team_name!r} is ambiguous. Matches: {choices}.")
        return dict(rows[0])

    def find_player_by_id(self, player_id: int) -> dict[str, Any]:
        """Resolve one player directly by MLB player ID."""
        query = text("""
        SELECT
            p.player_id,
            p.full_name,
            p.bats,
            p.throws,
            p.position_code,
            p.current_team_id,
            t.team_name,
            t.abbreviation AS team_abbreviation
        FROM public.players AS p
        LEFT JOIN public.teams AS t ON t.team_id = p.current_team_id
        WHERE p.player_id = :player_id
        LIMIT 1
        """)
        with get_engine().connect() as connection:
            row = connection.execute(
                query,
                {"player_id": int(player_id)},
            ).mappings().first()
        if not row:
            raise ValueError(f"No player was found with player ID {player_id}.")
        return dict(row)

    def find_player_by_name(
        self,
        player_name: str,
        team_id: int | None = None,
    ) -> dict[str, Any]:
        """Resolve one player by name, optionally preferring the selected team.

        A value containing only digits is treated as an MLB player ID. This
        allows ``--lineup`` to mix names and IDs when a name is ambiguous.
        """
        import unicodedata

        cleaned = " ".join(str(player_name).strip().split())
        if not cleaned:
            raise ValueError("A player name or player ID is required.")
        if cleaned.isdigit():
            row = self.find_player_by_id(int(cleaned))
            if team_id is not None and row.get("current_team_id") not in (None, int(team_id)):
                raise ValueError(
                    f"Player {row['full_name']} ({row['player_id']}) does not belong "
                    f"to selected team ID {team_id}."
                )
            return row

        def normalized(value: str) -> str:
            decomposed = unicodedata.normalize("NFKD", value)
            return " ".join(
                "".join(ch for ch in decomposed if not unicodedata.combining(ch))
                .casefold()
                .split()
            )

        surname = cleaned.split()[-1]

        # Build the ordering clause separately. Passing ``None`` into a CASE
        # expression caused PostgreSQL/psycopg to raise AmbiguousParameter
        # because it could not infer the SQL type of the null bind value.
        if team_id is None:
            query = text("""
            SELECT
                p.player_id,
                p.full_name,
                p.bats,
                p.throws,
                p.position_code,
                p.current_team_id,
                t.team_name,
                t.abbreviation AS team_abbreviation
            FROM public.players AS p
            LEFT JOIN public.teams AS t ON t.team_id = p.current_team_id
            WHERE LOWER(p.full_name) LIKE LOWER(:contains)
               OR LOWER(p.full_name) LIKE LOWER(:surname)
            ORDER BY p.full_name, p.player_id
            LIMIT 50
            """)
            parameters = {
                "contains": f"%{cleaned}%",
                "surname": f"%{surname}%",
            }
        else:
            query = text("""
            SELECT
                p.player_id,
                p.full_name,
                p.bats,
                p.throws,
                p.position_code,
                p.current_team_id,
                t.team_name,
                t.abbreviation AS team_abbreviation
            FROM public.players AS p
            LEFT JOIN public.teams AS t ON t.team_id = p.current_team_id
            WHERE LOWER(p.full_name) LIKE LOWER(:contains)
               OR LOWER(p.full_name) LIKE LOWER(:surname)
            ORDER BY
                CASE WHEN p.current_team_id = :team_id THEN 0 ELSE 1 END,
                p.full_name,
                p.player_id
            LIMIT 50
            """)
            parameters = {
                "contains": f"%{cleaned}%",
                "surname": f"%{surname}%",
                "team_id": int(team_id),
            }

        with get_engine().connect() as connection:
            rows = connection.execute(query, parameters).mappings().all()
        if not rows:
            raise ValueError(f"No player was found matching {player_name!r}.")

        target = normalized(cleaned)
        exact = [row for row in rows if normalized(str(row["full_name"])) == target]
        contains = [row for row in rows if target in normalized(str(row["full_name"]))]
        candidates = exact or contains or rows

        if team_id is not None:
            team_matches = [
                row for row in candidates
                if row.get("current_team_id") is not None
                and int(row["current_team_id"]) == int(team_id)
            ]
            if len(team_matches) == 1:
                return dict(team_matches[0])
            if len(team_matches) > 1:
                candidates = team_matches

        if len(candidates) == 1:
            return dict(candidates[0])

        choices = ", ".join(
            f"{row['full_name']} ({row['player_id']}, {row.get('team_name') or 'no team'})"
            for row in candidates[:8]
        )
        raise ValueError(
            f"Player name {player_name!r} is ambiguous. Matches: {choices}. "
            "Use a numeric player ID in the same --lineup value."
        )

    def find_players_by_names(
        self,
        player_names: Sequence[str],
        team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Resolve names/IDs while preserving batting-order order."""
        return [self.find_player_by_name(value, team_id=team_id) for value in player_names]

    def get_pitcher_metadata(self, pitcher_id: int) -> dict[str, Any]:
        query = text("""
        SELECT
            p.player_id,
            p.full_name AS pitcher_name,
            p.throws,
            p.current_team_id,
            t.team_name,
            t.abbreviation AS team_abbreviation
        FROM public.players AS p
        LEFT JOIN public.teams AS t ON t.team_id = p.current_team_id
        WHERE p.player_id = :pitcher_id
        LIMIT 1
        """)
        with get_engine().connect() as connection:
            row = connection.execute(query, {"pitcher_id": int(pitcher_id)}).mappings().first()
        if not row:
            return {
                "player_id": int(pitcher_id),
                "pitcher_name": f"Pitcher {pitcher_id}",
                "throws": "",
                "team_name": "",
            }
        return dict(row)


    def get_opponent_team_from_game_pitches(
        self,
        game_pk: int,
        pitcher_id: int,
    ) -> int | None:
        """Infer the opponent from batters actually faced in the selected game.

        This is a fallback for historical games when the player's current team
        is missing or no longer matches the game because of a trade.
        """
        query = text("""
        SELECT
            sl.team_id,
            COUNT(*) AS matched_pitches
        FROM public.statcast_pitches AS sp
        JOIN public.starting_lineups AS sl
          ON sl.game_pk = sp.game_pk
         AND sl.player_id = sp.batter_id
        WHERE sp.game_pk = :game_pk
          AND sp.pitcher_id = :pitcher_id
        GROUP BY sl.team_id
        ORDER BY matched_pitches DESC
        LIMIT 1
        """)
        with get_engine().connect() as connection:
            row = connection.execute(
                query,
                {"game_pk": int(game_pk), "pitcher_id": int(pitcher_id)},
            ).mappings().first()
        return int(row["team_id"]) if row and row.get("team_id") is not None else None

    def get_game_lineup_team_ids(self, game_pk: int) -> list[int]:
        """Return team IDs with stored starting lineups for a game."""
        query = text("""
        SELECT DISTINCT team_id
        FROM public.starting_lineups
        WHERE game_pk = :game_pk
        ORDER BY team_id
        """)
        with get_engine().connect() as connection:
            rows = connection.execute(query, {"game_pk": int(game_pk)}).mappings().all()
        return [int(row["team_id"]) for row in rows if row.get("team_id") is not None]

    def get_pitcher_history(
        self,
        pitcher_id: int,
        filters: HistoryFilters,
    ) -> pd.DataFrame:
        query = f"""
        SELECT
        {PITCH_COLUMNS},
            batter.bats AS batter_side,
            batter.full_name AS batter_name
        FROM public.statcast_pitches AS sp
        LEFT JOIN public.players AS batter ON batter.player_id = sp.batter_id
        WHERE sp.pitcher_id = :pitcher_id
          AND sp.pitch_type IS NOT NULL
        """
        params: dict[str, Any] = {"pitcher_id": int(pitcher_id)}
        query, params = self._append_history_filters(query, params, filters)
        query += """
        ORDER BY sp.game_date, sp.game_pk, sp.at_bat_number, sp.pitch_number
        """
        with get_engine().connect() as connection:
            return pd.read_sql(text(query), connection, params=params)

    def get_batter_histories(
        self,
        batter_ids: Sequence[int],
        filters: HistoryFilters,
    ) -> pd.DataFrame:
        cleaned_ids = sorted({int(value) for value in batter_ids})
        if not cleaned_ids:
            return pd.DataFrame()
        query = f"""
        SELECT
        {PITCH_COLUMNS},
            pitcher.throws AS pitcher_throws,
            batter.bats AS batter_side,
            batter.full_name AS batter_name
        FROM public.statcast_pitches AS sp
        LEFT JOIN public.players AS pitcher ON pitcher.player_id = sp.pitcher_id
        LEFT JOIN public.players AS batter ON batter.player_id = sp.batter_id
        WHERE sp.batter_id IN :batter_ids
        """
        params: dict[str, Any] = {"batter_ids": cleaned_ids}
        query, params = self._append_history_filters(query, params, filters)
        query += """
        ORDER BY sp.batter_id, sp.game_date, sp.game_pk, sp.at_bat_number, sp.pitch_number
        """
        statement = text(query).bindparams(bindparam("batter_ids", expanding=True))
        with get_engine().connect() as connection:
            return pd.read_sql(statement, connection, params=params)

    def get_direct_matchups(
        self,
        pitcher_id: int,
        batter_ids: Sequence[int],
        filters: HistoryFilters,
    ) -> pd.DataFrame:
        cleaned_ids = sorted({int(value) for value in batter_ids})
        if not cleaned_ids:
            return pd.DataFrame()
        query = f"""
        SELECT
        {PITCH_COLUMNS},
            pitcher.throws AS pitcher_throws,
            batter.bats AS batter_side,
            batter.full_name AS batter_name
        FROM public.statcast_pitches AS sp
        LEFT JOIN public.players AS pitcher ON pitcher.player_id = sp.pitcher_id
        LEFT JOIN public.players AS batter ON batter.player_id = sp.batter_id
        WHERE sp.pitcher_id = :pitcher_id
          AND sp.batter_id IN :batter_ids
        """
        params: dict[str, Any] = {
            "pitcher_id": int(pitcher_id),
            "batter_ids": cleaned_ids,
        }
        query, params = self._append_history_filters(query, params, filters)
        query += """
        ORDER BY sp.batter_id, sp.game_date, sp.game_pk, sp.at_bat_number, sp.pitch_number
        """
        statement = text(query).bindparams(bindparam("batter_ids", expanding=True))
        with get_engine().connect() as connection:
            return pd.read_sql(statement, connection, params=params)
