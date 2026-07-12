from analytics.database import (
    test_database_connection as check_database_connection,
)
from analytics.repository import BaseballRepository


def test_database_connection() -> None:
    """Confirm that PostgreSQL accepts a connection."""
    result = check_database_connection()

    assert isinstance(result, dict)
    assert result["database_name"]
    assert result["database_user"]
    assert result["server_time"]


def test_can_connect_to_database() -> None:
    """Confirm that expected database metadata is returned."""
    result = check_database_connection()

    assert result["database_name"] is not None
    assert result["database_user"] is not None
    assert result["postgres_version"] is not None
    assert result["server_time"] is not None


def test_core_tables_are_accessible() -> None:
    """Confirm that every required warehouse table can be queried."""
    repository = BaseballRepository()
    counts = repository.get_table_counts()

    expected_tables = {
        "games",
        "parks",
        "players",
        "starting_lineups",
        "statcast_pitches",
        "teams",
        "transactions",
        "umpires",
    }

    actual_tables = set(counts["table_name"].tolist())

    assert expected_tables == actual_tables
    assert counts["row_count"].notna().all()
    assert (counts["row_count"] >= 0).all()


def test_team_and_park_queries() -> None:
    """Confirm that core dimension queries return expected columns."""
    repository = BaseballRepository()

    teams = repository.get_teams()
    parks = repository.get_parks()

    assert "team_id" in teams.columns
    assert "team_name" in teams.columns
    assert "park_id" in parks.columns
    assert "park_name" in parks.columns