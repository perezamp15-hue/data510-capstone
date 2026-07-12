import pytest
from analytics.exceptions import ValidationError
from analytics.repository import BaseballRepository

def test_available_seasons_are_sorted_descending() -> None:
    repository = BaseballRepository()
    seasons = repository.get_available_seasons()

    assert seasons == sorted(seasons, reverse=True)

def test_player_search_requires_two_characters() -> None:
    repository = BaseballRepository()

    with pytest.raises(ValidationError):
        repository.search_players("A")

def test_invalid_player_id_is_rejected() -> None:
    repository = BaseballRepository()

    with pytest.raises(ValidationError):
        repository.get_player(0)

def test_recent_games_limit_is_validated() -> None:
    repository = BaseballRepository()

    with pytest.raises(ValidationError):
        repository.get_recent_games(limit=0)