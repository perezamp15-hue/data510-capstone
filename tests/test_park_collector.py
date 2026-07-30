"""Tests for MLB park parsing."""

from __future__ import annotations

from typing import Any

import pytest

from baseball_capstone.collectors.client import MLBAPIError
from baseball_capstone.collectors.parks import (
    ParkRecord,
    ParkValidationError,
    deduplicate_parks,
    fetch_team_venues,
    parse_team_park,
)


class FakeMLBClient:
    """Small fake MLB API client."""

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


def test_parse_team_park() -> None:
    raw_team = {
        "id": 119,
        "name": "Los Angeles Dodgers",
        "venue": {
            "id": 22,
            "name": "Dodger Stadium",
            "location": {
                "city": "Los Angeles",
                "stateAbbrev": "CA",
                "country": "USA",
            },
            "timeZone": {
                "id": "America/Los_Angeles",
            },
        },
    }

    park, assignment = parse_team_park(raw_team)

    assert park.park_id == 22
    assert park.name == "Dodger Stadium"
    assert park.city == "Los Angeles"
    assert park.state == "CA"
    assert park.country == "USA"
    assert park.time_zone == "America/Los_Angeles"

    assert assignment.team_id == 119
    assert assignment.park_id == 22


def test_parse_team_park_rejects_missing_team_id() -> None:
    raw_team = {
        "venue": {
            "id": 22,
            "name": "Dodger Stadium",
        }
    }

    with pytest.raises(ParkValidationError):
        parse_team_park(raw_team)


def test_parse_team_park_rejects_missing_venue() -> None:
    raw_team = {
        "id": 119,
        "name": "Los Angeles Dodgers",
    }

    with pytest.raises(ParkValidationError):
        parse_team_park(raw_team)


def test_parse_team_park_rejects_missing_venue_id() -> None:
    raw_team = {
        "id": 119,
        "venue": {
            "name": "Dodger Stadium",
        },
    }

    with pytest.raises(ParkValidationError):
        parse_team_park(raw_team)


def test_deduplicate_parks_keeps_one_record_per_id() -> None:
    records = [
        ParkRecord(
            park_id=22,
            name="Dodger Stadium",
            city="Los Angeles",
            state="CA",
            country="USA",
            time_zone="America/Los_Angeles",
            elevation_feet=None,
        ),
        ParkRecord(
            park_id=22,
            name="Dodger Stadium",
            city="Los Angeles",
            state="CA",
            country="USA",
            time_zone="America/Los_Angeles",
            elevation_feet=515,
        ),
    ]

    result = deduplicate_parks(records)

    assert len(result) == 1
    assert result[0].park_id == 22
    assert result[0].elevation_feet == 515


def test_fetch_team_venues_returns_team_list() -> None:
    fake_client = FakeMLBClient(
        {
            "teams": [
                {
                    "id": 119,
                    "venue": {
                        "id": 22,
                        "name": "Dodger Stadium",
                    },
                }
            ]
        }
    )

    result = fetch_team_venues(fake_client)  # type: ignore[arg-type]

    assert len(result) == 1
    assert fake_client.endpoint == "/v1/teams"
    assert fake_client.params is not None
    assert fake_client.params["sportId"] == 1
    assert fake_client.params["hydrate"] == "venue"


def test_fetch_team_venues_rejects_invalid_response() -> None:
    fake_client = FakeMLBClient(
        {
            "message": "Unexpected response",
        }
    )

    with pytest.raises(MLBAPIError):
        fetch_team_venues(fake_client)  # type: ignore[arg-type]