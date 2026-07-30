"""Tests for player collection parsing."""

from datetime import date

import pytest

from baseball_capstone.collectors.players import (
    PlayerRecord,
    PlayerValidationError,
    deduplicate_players,
    optional_date,
    parse_player,
)


def test_optional_date_parses_iso_date() -> None:
    assert optional_date("1994-07-05") == date(
        1994,
        7,
        5,
    )


def test_optional_date_returns_none_for_invalid_value() -> None:
    assert optional_date("not-a-date") is None


def test_parse_player_combines_roster_and_profile() -> None:
    roster_entry = {
        "person": {
            "id": 660271,
            "fullName": "Shohei Ohtani",
        },
        "jerseyNumber": "17",
        "position": {
            "code": "Y",
            "name": "Two-Way Player",
            "type": "Two-Way Player",
            "abbreviation": "TWP",
        },
        "status": {
            "code": "A",
            "description": "Active",
        },
    }

    profile = {
        "id": 660271,
        "fullName": "Shohei Ohtani",
        "firstName": "Shohei",
        "lastName": "Ohtani",
        "useName": "Shohei",
        "birthDate": "1994-07-05",
        "mlbDebutDate": "2018-03-29",
        "height": "6' 4\"",
        "weight": 210,
        "active": True,
        "batSide": {
            "code": "L",
        },
        "pitchHand": {
            "code": "R",
        },
        "primaryPosition": {
            "code": "Y",
            "name": "Two-Way Player",
            "type": "Two-Way Player",
            "abbreviation": "TWP",
        },
    }

    result = parse_player(
        roster_entry=roster_entry,
        profile=profile,
        team_id=119,
    )

    assert result.player_id == 660271
    assert result.full_name == "Shohei Ohtani"
    assert result.current_team_id == 119
    assert result.bats == "L"
    assert result.throws == "R"
    assert result.primary_position == "TWP"
    assert result.jersey_number == "17"


def test_parse_player_rejects_missing_id() -> None:
    with pytest.raises(PlayerValidationError):
        parse_player(
            roster_entry={},
            profile={"fullName": "Unknown Player"},
            team_id=119,
        )


def test_deduplicate_players_keeps_latest_record() -> None:
    base_values = {
        "player_id": 1,
        "full_name": "Example Player",
        "first_name": "Example",
        "last_name": "Player",
        "use_name": "Example",
        "primary_position": "P",
        "position_name": "Pitcher",
        "position_type": "Pitcher",
        "bats": "R",
        "throws": "R",
        "birth_date": None,
        "mlb_debut_date": None,
        "height": None,
        "weight": None,
        "jersey_number": None,
        "active": True,
        "roster_status": "A",
        "last_roster_check_at": None,
    }

    first = PlayerRecord(
        **base_values,
        current_team_id=119,
    )

    second = PlayerRecord(
        **base_values,
        current_team_id=147,
    )

    result = deduplicate_players([first, second])

    assert len(result) == 1
    assert result[0].current_team_id == 147