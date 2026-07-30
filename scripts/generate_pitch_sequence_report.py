"""Generate a real two-team pitch strategy HTML report."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.analytics.game_plan_data import (
    build_team_plan,
    get_player_profile,
    get_players,
)
from baseball_capstone.reports.html_report import (
    render_two_team_game_plan,
)


def parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; use YYYY-MM-DD."
        ) from exc


def parse_player_ids(value: str) -> list[int]:
    """Parse a comma-separated lineup."""
    try:
        player_ids = [
            int(item.strip())
            for item in value.split(",")
            if item.strip()
        ]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Lineup IDs must be comma-separated integers."
        ) from exc

    if len(player_ids) != 9:
        raise argparse.ArgumentTypeError(
            "Each lineup must contain exactly nine player IDs."
        )

    if len(player_ids) != len(set(player_ids)):
        raise argparse.ArgumentTypeError(
            "Each lineup must contain nine unique player IDs."
        )

    return player_ids


def parse_arguments() -> argparse.Namespace:
    """Parse live report inputs."""
    parser = argparse.ArgumentParser(
        description="Generate a two-team pitch strategy HTML report."
    )

    parser.add_argument("--away-team", required=True)
    parser.add_argument(
        "--away-pitcher-id",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--away-lineup-ids",
        type=parse_player_ids,
        required=True,
    )

    parser.add_argument("--home-team", required=True)
    parser.add_argument(
        "--home-pitcher-id",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--home-lineup-ids",
        type=parse_player_ids,
        required=True,
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        required=True,
    )
    parser.add_argument(
        "--end-date",
        type=parse_date,
        required=True,
    )

    parser.add_argument(
        "--venue",
        default="Not supplied",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    """Build and render the live game plan."""
    arguments = parse_arguments()

    if arguments.end_date < arguments.start_date:
        print("The end date cannot be before the start date.")
        return 1

    try:
        away_pitcher = get_player_profile(
            arguments.away_pitcher_id
        )
        home_pitcher = get_player_profile(
            arguments.home_pitcher_id
        )

        away_lineup = get_players(
            arguments.away_lineup_ids
        )
        home_lineup = get_players(
            arguments.home_lineup_ids
        )

        # Away offense faces the home starting pitcher.
        away_offense_plan = build_team_plan(
            offense_team=arguments.away_team,
            opposing_pitcher=home_pitcher,
            lineup=away_lineup,
            start_date=arguments.start_date,
            end_date=arguments.end_date,
        )

        # Home offense faces the away starting pitcher.
        home_offense_plan = build_team_plan(
            offense_team=arguments.home_team,
            opposing_pitcher=away_pitcher,
            lineup=home_lineup,
            start_date=arguments.start_date,
            end_date=arguments.end_date,
        )

        report_data = {
            "report_title": "Two-Team Pitch Strategy Report",
            "model_version": (
                "frequency-baseline + rules-optimizer-v1"
            ),
            "venue": arguments.venue,
            "data_period": (
                f"{arguments.start_date} through "
                f"{arguments.end_date}"
            ),
            "away_team": {
                "name": arguments.away_team,
                "pitcher": {
                    "player_id": away_pitcher.player_id,
                    "name": away_pitcher.name,
                    "throws": away_pitcher.throws or "Unknown",
                },
            },
            "home_team": {
                "name": arguments.home_team,
                "pitcher": {
                    "player_id": home_pitcher.player_id,
                    "name": home_pitcher.name,
                    "throws": home_pitcher.throws or "Unknown",
                },
            },
            "team_plans": [
                away_offense_plan,
                home_offense_plan,
            ],
            "methodology": [
                (
                    "Player identity, handedness, pitch arsenal, "
                    "and batter splits are queried from PostgreSQL."
                ),
                (
                    "First-pitch probabilities use a hierarchical "
                    "historical frequency baseline."
                ),
                (
                    "Three-pitch recommendations are restricted to "
                    "the opposing pitcher's qualifying arsenal."
                ),
                (
                    "The current optimizer is rules-based and will "
                    "be replaced or enhanced after model training."
                ),
                (
                    "Minimum qualifying arsenal thresholds are five "
                    "percent usage and 25 observed pitches."
                ),
            ],
        }

        output_path = render_two_team_game_plan(
            output_path=arguments.output,
            report_data=report_data,
        )

    except Exception as exc:
        print(f"Report generation failed: {exc}")
        return 1

    print(f"Two-team HTML report created: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())