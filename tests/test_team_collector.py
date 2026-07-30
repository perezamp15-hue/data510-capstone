"""Tests for MLB team parsing and API response handling."""

from __future__ import annotations

from typing import Any

import pytest

from baseball_capstone.collectors.client import MLBAPIError
from baseball_capstone.collectors.teams import (
    TeamValidationError,
    fetch_teams,
    parse_team,
)


class FakeMLBClient:
    """Minimal fake client for collector tests."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.endpoint: str | None = None
        self.params: dict[str, Any] | None = None

    def get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.endpoint = endpoint
        self.params = params
        return self.payload


def test_parse_team_returns_normalized_record() -> None:
    raw_team = {
        "id": 119,
        "name": "Los Angeles Dodgers",
        "abbreviation": "LAD",
        "active": True,
        "league": {
            "name": "National League",
        },
        "division": {
            "name": "National League West",
        },
    }

    result = parse_team(raw_team)

    assert result.team_id == 119
    assert result.name == "Los Angeles Dodgers"
    assert result.abbreviation == "LAD"
    assert result.league_name == "National League"
    assert result.division_name == "National League West"
    assert result.active is True


def test_parse_team_rejects_missing_id() -> None:
    raw_team = {
        "name": "Invalid Team",
    }

    with pytest.raises(TeamValidationError):
        parse_team(raw_team)


def test_parse_team_rejects_missing_name() -> None:
    raw_team = {
        "id": 999,
        "name": " ",
    }

    with pytest.raises(TeamValidationError):
        parse_team(raw_team)


def test_fetch_teams_returns_team_list() -> None:
    fake_client = FakeMLBClient(
        {
            "teams": [
                {
                    "id": 119,
                    "name": "Los Angeles Dodgers",
                }
            ]
        }
    )

    result = fetch_teams(fake_client)  # type: ignore[arg-type]

    assert len(result) == 1
    assert result[0]["id"] == 119
    assert fake_client.endpoint == "/v1/teams"
    assert fake_client.params is not None
    assert fake_client.params["sportId"] == 1


def test_fetch_teams_rejects_missing_team_list() -> None:
    fake_client = FakeMLBClient(
        {
            "message": "Unexpected response",
        }
    )

    with pytest.raises(MLBAPIError):
        fetch_teams(fake_client)  # type: ignore[arg-type]