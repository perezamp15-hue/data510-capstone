"""Generate a demonstration two-team pitch strategy report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.reports.html_report import (
    render_two_team_game_plan,
)


def parse_arguments() -> argparse.Namespace:
    """Parse report output options."""
    parser = argparse.ArgumentParser(
        description="Generate a two-team HTML game plan."
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "output/two_team_pitch_strategy_demo.html"
        ),
    )

    return parser.parse_args()


def make_batter(
    *,
    order: int,
    player_id: int,
    name: str,
    bats: str,
    threat_level: str,
    primary_pitch: str,
    second_pitch: str,
    third_pitch: str,
) -> dict:
    """Build one demonstration batter plan."""
    return {
        "order": order,
        "player_id": player_id,
        "name": name,
        "bats": bats,
        "threat_level": threat_level,
        "historical_sample": 320 + order * 17,
        "confidence": 0.68 + order * 0.015,
        "predicted_pitches": [
            {
                "pitch_name": primary_pitch,
                "probability": 0.43,
            },
            {
                "pitch_name": second_pitch,
                "probability": 0.31,
            },
            {
                "pitch_name": third_pitch,
                "probability": 0.18,
            },
            {
                "pitch_name": "Other",
                "probability": 0.08,
            },
        ],
        "recommended_sequence": {
            "score": 82.0 + order,
            "expected_woba": 0.265 + order * 0.002,
            "whiff_probability": 0.29 + order * 0.003,
            "pitches": [
                {
                    "pitch_name": primary_pitch,
                    "zone": "Upper third",
                    "reason": (
                        "Establish the highest-value pitch "
                        "without entering the heart of the zone."
                    ),
                },
                {
                    "pitch_name": second_pitch,
                    "zone": "Down and away",
                    "reason": (
                        "Create movement and location separation."
                    ),
                },
                {
                    "pitch_name": third_pitch,
                    "zone": "Below the zone",
                    "reason": (
                        "Use as the chase or put-away pitch."
                    ),
                },
            ],
        },
        "adjustments": [
            "Behind in the count: favor the highest-command pitch.",
            "Ahead with two strikes: expand below or away.",
            "Avoid the middle third with runners in scoring position.",
        ],
        "strategy_summary": (
            f"Use {primary_pitch} to establish the matchup, "
            f"then separate with {second_pitch}. Finish with "
            f"{third_pitch} outside the batter's strongest zone."
        ),
    }


def build_demo_data() -> dict:
    """Create two complete demonstration lineup plans."""
    away_lineup = [
        make_batter(
            order=index,
            player_id=700000 + index,
            name=f"Away Batter {index}",
            bats="L" if index % 2 else "R",
            threat_level=(
                "High"
                if index in {2, 3, 4}
                else "Medium"
            ),
            primary_pitch="Four-seam",
            second_pitch="Slider",
            third_pitch="Changeup",
        )
        for index in range(1, 10)
    ]

    home_lineup = [
        make_batter(
            order=index,
            player_id=710000 + index,
            name=f"Home Batter {index}",
            bats="R" if index % 2 else "L",
            threat_level=(
                "High"
                if index in {3, 4, 5}
                else "Medium"
            ),
            primary_pitch="Sinker",
            second_pitch="Sweeper",
            third_pitch="Splitter",
        )
        for index in range(1, 10)
    ]

    return {
        "report_title": "Two-Team Pitch Strategy Report",
        "model_version": "development-demo",
        "venue": "Example Ballpark",
        "data_period": "2025–2026",
        "away_team": {
            "name": "Away Team",
            "pitcher": {
                "player_id": 600001,
                "name": "Away Starting Pitcher",
                "throws": "R",
            },
        },
        "home_team": {
            "name": "Home Team",
            "pitcher": {
                "player_id": 600002,
                "name": "Home Starting Pitcher",
                "throws": "L",
            },
        },
        "team_plans": [
            {
                "offense_team": "Away Team",
                "opposing_pitcher": {
                    "name": "Home Starting Pitcher",
                    "throws": "L",
                },
                "lineup": away_lineup,
                "team_summary": [
                    "Expect elevated fastballs early in counts.",
                    "Left-handed hitters should prepare for sliders away.",
                    "Protect below the zone with two strikes.",
                    "Avoid expanding against secondary pitches when behind.",
                ],
            },
            {
                "offense_team": "Home Team",
                "opposing_pitcher": {
                    "name": "Away Starting Pitcher",
                    "throws": "R",
                },
                "lineup": home_lineup,
                "team_summary": [
                    "Expect sinkers inside against right-handed hitters.",
                    "Look for sweepers after first-pitch strikes.",
                    "Force the pitcher into fastball counts.",
                    "Do not chase splitters below the strike zone.",
                ],
            },
        ],
        "methodology": [
            (
                "Each lineup is evaluated batter by batter against "
                "the opposing starting pitcher."
            ),
            (
                "Pitch-type probabilities will come from the "
                "next-pitch prediction model."
            ),
            (
                "Pitch-location recommendations will use catcher-view "
                "zones and batter-relative inside/outside labels."
            ),
            (
                "Recommended sequences will be limited to pitches "
                "in the opposing pitcher's observed arsenal."
            ),
            (
                "Current values are placeholders until historical "
                "backfill and final model training are complete."
            ),
        ],
    }


def main() -> int:
    """Generate the two-team demonstration report."""
    arguments = parse_arguments()

    try:
        output_path = render_two_team_game_plan(
            output_path=arguments.output,
            report_data=build_demo_data(),
        )
    except Exception as exc:
        print(f"Report generation failed: {exc}")
        return 1

    print(f"Two-team HTML report created: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())