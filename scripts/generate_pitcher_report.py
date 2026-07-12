from __future__ import annotations
import argparse
from pathlib import Path
from analytics.pitcher_profile import build_pitcher_profile
from analytics.report_builder import build_pitcher_report
from analytics.repository import BaseballRepository
from visualizations.pitcher_report_card import (
    create_pitcher_report_card,
)

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a pitcher scouting report graphic."
        )
    )

    parser.add_argument(
        "--pitcher-id",
        type=int,
        required=True,
        help="MLB pitcher ID.",
    )

    parser.add_argument(
        "--season",
        type=int,
        required=True,
        help="Season to analyze.",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional output PNG path.",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Display the graphic after generation.",
    )

    return parser.parse_args()

def main() -> None:
    arguments = parse_arguments()

    repository = BaseballRepository()

    pitches = repository.get_pitcher_pitches(
        pitcher_id=arguments.pitcher_id,
        season=arguments.season,
    )

    if pitches.empty:
        raise ValueError(
            "No pitch data was found for "
            f"pitcher_id={arguments.pitcher_id}, "
            f"season={arguments.season}."
        )

    profile = build_pitcher_profile(
        pitches
    )

    report = build_pitcher_report(
        profile
    )

    if arguments.output:
        output_path = Path(
            arguments.output
        )

    else:
        output_path = Path(
            "output"
        ) / (
            f"pitcher_report_"
            f"{arguments.pitcher_id}_"
            f"{arguments.season}.png"
        )
    final_path = create_pitcher_report_card(
        report=report,
        output_path=output_path,
        show=arguments.show,
    )
    print(
        "Pitcher report created successfully:"
    )
    print(
        final_path.resolve()
    )

if __name__ == "__main__":
    main()