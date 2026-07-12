from __future__ import annotations
from datetime import date, datetime
from typing import Any
import pandas as pd
from analytics import queries
from analytics.database import read_dataframe, read_scalar
from analytics.exceptions import DataNotFoundError, ValidationError
from analytics.validation import (
    validate_date,
    validate_date_range,
    validate_limit,
    validate_positive_id,
    validate_season,
)


class BaseballRepository:
    # DATABASE STATUS
    def get_table_counts(self) -> pd.DataFrame:
        """Return row counts for all core tables."""
        return read_dataframe(queries.TABLE_COUNTS_QUERY)

    def get_available_seasons(self) -> list[int]:
        """Return all seasons currently stored in the games table."""
        frame = read_dataframe(queries.AVAILABLE_SEASONS_QUERY)

        if frame.empty:
            return []

        return frame["season"].dropna().astype(int).tolist()

    def get_latest_game_date(self) -> date | None:
        """Return the latest game date in the database."""
        result = read_scalar(queries.LATEST_GAME_DATE_QUERY)

        if result is None:
            return None

        if isinstance(result, datetime):
            return result.date()

        return result

    # PLAYERS
    def get_player(self, player_id: int) -> dict[str, Any]:
        """Return one player and current team information."""
        validate_positive_id(player_id, "player_id")

        frame = read_dataframe(
            queries.PLAYER_BY_ID_QUERY,
            {"player_id": player_id},
        )

        if frame.empty:
            raise DataNotFoundError(
                f"No player was found for player_id={player_id}."
            )

        return frame.iloc[0].to_dict()

    def search_players(
        self,
        search_text: str,
        limit: int = 25,
    ) -> pd.DataFrame:
        """Search players by partial name."""
        if not isinstance(search_text, str):
            raise ValidationError("search_text must be a string.")

        cleaned = search_text.strip()

        if len(cleaned) < 2:
            raise ValidationError(
                "search_text must contain at least two characters."
            )

        validate_limit(limit, maximum=100)

        return read_dataframe(
            queries.SEARCH_PLAYERS_QUERY,
            {
                "search_pattern": f"%{cleaned}%",
                "limit": limit,
            },
        )

    def get_active_players(self, limit: int = 2000) -> pd.DataFrame:
        """Return active players."""
        validate_limit(limit, maximum=5000)

        return read_dataframe(
            queries.ACTIVE_PLAYERS_QUERY,
            {"limit": limit},
        )

    # PITCH DATA
    def get_pitcher_pitches(
        self,
        pitcher_id: int,
        season: int | None = None,
        start_date: date | datetime | str | None = None,
        end_date: date | datetime | str | None = None,
    ) -> pd.DataFrame:
        """Return all selected pitches thrown by one pitcher."""
        validate_positive_id(pitcher_id, "pitcher_id")

        if season is not None:
            validate_season(season)

        parsed_start, parsed_end = validate_date_range(
            start_date,
            end_date,
        )

        return read_dataframe(
            queries.PITCHER_PITCHES_QUERY,
            {
                "pitcher_id": pitcher_id,
                "season": season,
                "start_date": parsed_start,
                "end_date": parsed_end,
            },
        )

    def get_batter_pitches(
        self,
        batter_id: int,
        season: int | None = None,
        start_date: date | datetime | str | None = None,
        end_date: date | datetime | str | None = None,
    ) -> pd.DataFrame:
        """Return all selected pitches faced by one batter."""
        validate_positive_id(batter_id, "batter_id")

        if season is not None:
            validate_season(season)

        parsed_start, parsed_end = validate_date_range(
            start_date,
            end_date,
        )

        return read_dataframe(
            queries.BATTER_PITCHES_QUERY,
            {
                "batter_id": batter_id,
                "season": season,
                "start_date": parsed_start,
                "end_date": parsed_end,
            },
        )

    def get_matchup_pitches(
        self,
        pitcher_id: int,
        batter_id: int,
        season: int | None = None,
    ) -> pd.DataFrame:
        """Return historical pitches for a pitcher-versus-batter matchup."""
        validate_positive_id(pitcher_id, "pitcher_id")
        validate_positive_id(batter_id, "batter_id")

        if season is not None:
            validate_season(season)

        return read_dataframe(
            queries.MATCHUP_PITCHES_QUERY,
            {
                "pitcher_id": pitcher_id,
                "batter_id": batter_id,
                "season": season,
            },
        )

    # GAMES
    def get_game(self, game_pk: int) -> dict[str, Any]:
        """Return one game with teams, park, weather, and umpires."""
        validate_positive_id(game_pk, "game_pk")

        frame = read_dataframe(
            queries.GAME_BY_ID_QUERY,
            {"game_pk": game_pk},
        )

        if frame.empty:
            raise DataNotFoundError(
                f"No game was found for game_pk={game_pk}."
            )

        return frame.iloc[0].to_dict()

    def get_games_by_date(
        self,
        game_date: date | datetime | str,
    ) -> pd.DataFrame:
        """Return all games played on a date."""
        parsed_date = validate_date(game_date, "game_date")

        return read_dataframe(
            queries.GAMES_BY_DATE_QUERY,
            {"game_date": parsed_date},
        )

    def get_recent_games(
        self,
        season: int | None = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        """Return recent games."""
        if season is not None:
            validate_season(season)

        validate_limit(limit, maximum=500)

        return read_dataframe(
            queries.RECENT_GAMES_QUERY,
            {
                "season": season,
                "limit": limit,
            },
        )

    def get_game_lineups(self, game_pk: int) -> pd.DataFrame:
        """Return both starting lineups for a game."""
        validate_positive_id(game_pk, "game_pk")

        return read_dataframe(
            queries.GAME_LINEUPS_QUERY,
            {"game_pk": game_pk},
        )

    # PARKS
    def get_parks(self) -> pd.DataFrame:
        """Return every park."""
        return read_dataframe(queries.PARKS_QUERY)

    def get_park(self, park_id: int) -> dict[str, Any]:
        """Return one park."""
        validate_positive_id(park_id, "park_id")

        frame = read_dataframe(
            queries.PARK_BY_ID_QUERY,
            {"park_id": park_id},
        )

        if frame.empty:
            raise DataNotFoundError(
                f"No park was found for park_id={park_id}."
            )

        return frame.iloc[0].to_dict()

    def get_park_games(
        self,
        park_id: int,
        season: int | None = None,
    ) -> pd.DataFrame:
        """Return games played at one park."""
        validate_positive_id(park_id, "park_id")

        if season is not None:
            validate_season(season)

        return read_dataframe(
            queries.PARK_GAMES_QUERY,
            {
                "park_id": park_id,
                "season": season,
            },
        )

    # TEAMS
    def get_teams(self) -> pd.DataFrame:
        """Return all teams."""
        return read_dataframe(queries.TEAMS_QUERY)

    def get_team(self, team_id: int) -> dict[str, Any]:
        """Return one team."""
        validate_positive_id(team_id, "team_id")

        frame = read_dataframe(
            queries.TEAM_BY_ID_QUERY,
            {"team_id": team_id},
        )

        if frame.empty:
            raise DataNotFoundError(
                f"No team was found for team_id={team_id}."
            )

        return frame.iloc[0].to_dict()

    # TRANSACTIONS
    def get_player_transactions(
        self,
        player_id: int,
    ) -> pd.DataFrame:
        """Return transaction and injury history for one player."""
        validate_positive_id(player_id, "player_id")

        return read_dataframe(
            queries.PLAYER_TRANSACTIONS_QUERY,
            {"player_id": player_id},
        )

    def get_recent_transactions(
        self,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Return recent transactions."""
        validate_limit(limit, maximum=1000)

        return read_dataframe(
            queries.RECENT_TRANSACTIONS_QUERY,
            {"limit": limit},
        )