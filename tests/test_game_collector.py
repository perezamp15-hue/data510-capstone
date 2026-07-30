"""Tests for MLB game schedule parsing."""

from datetime import date

import pytest

from baseball_capstone.collectors.games import (
    GameValidationError,
    parse_game,
    parse_iso_datetime,
    parse_wind,
)


def test_parse_iso_datetime() -> None:
    result = parse_iso_datetime("2026-07-20T23:10:00Z")

    assert result is not None
    assert result.year == 2026
    assert result.month == 7
    assert result.day == 20


def test_parse_wind() -> None:
    speed, direction = parse_wind(
        {"wind": "8 mph, Out To RF"}
    )

    assert speed == 8
    assert direction == "Out To RF"


def test_parse_game() -> None:
    raw_game = {
        "gamePk": 777001,
        "gameDate": "2026-07-20T23:10:00Z",
        "officialDate": "2026-07-20",
        "season": "2026",
        "gameType": "R",
        "doubleHeader": "N",
        "gameNumber": 1,
        "dayNight": "night",
        "status": {
            "statusCode": "F",
            "detailedState": "Final",
            "abstractGameState": "Final",
        },
        "venue": {
            "id": 22,
            "name": "Dodger Stadium",
        },
        "teams": {
            "away": {
                "team": {
                    "id": 116,
                },
                "score": 2,
                "probablePitcher": {
                    "id": 669373,
                },
            },
            "home": {
                "team": {
                    "id": 119,
                },
                "score": 5,
                "probablePitcher": {
                    "id": 694973,
                },
            },
        },
        "linescore": {
            "currentInning": 9,
            "inningHalf": "Bottom",
        },
        "weather": {
            "temp": 74,
            "condition": "Clear",
            "wind": "5 mph, Out To RF",
        },
    }

    result = parse_game(raw_game)

    assert result.game_pk == 777001
    assert result.game_date == date(2026, 7, 20)
    assert result.home_team_id == 119
    assert result.away_team_id == 116
    assert result.home_score == 5
    assert result.away_score == 2
    assert result.home_probable_pitcher_id == 694973
    assert result.temperature_f == 74
    assert result.wind_speed_mph == 5


def test_parse_game_rejects_missing_game_pk() -> None:
    with pytest.raises(GameValidationError):
        parse_game(
            {
                "officialDate": "2026-07-20",
                "teams": {},
            }
        )


def test_parse_game_rejects_missing_team() -> None:
    with pytest.raises(GameValidationError):
        parse_game(
            {
                "gamePk": 777001,
                "officialDate": "2026-07-20",
                "season": "2026",
                "teams": {
                    "home": {
                        "team": {
                            "id": 119,
                        }
                    },
                    "away": {},
                },
            }
        )