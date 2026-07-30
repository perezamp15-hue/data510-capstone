"""Generate a two-team statistical baseball scouting report."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from baseball_capstone.analytics.statistical_scouting import (  # noqa: E402
    PlayerLookupError,
    build_statistical_report,
)
from baseball_capstone.database.engine import get_engine  # noqa: E402
from baseball_capstone.reports.statistical_html_report import (  # noqa: E402
    render_pdf_from_html,
    render_statistical_scouting_report,
)


def comma_separated_names(raw: str) -> list[str]:
    names = [name.strip() for name in raw.split(",") if name.strip()]
    if len(names) != 9:
        raise argparse.ArgumentTypeError(
            f"Expected exactly nine comma-separated player names; received {len(names)}."
        )
    return names


def iso_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Dates must use YYYY-MM-DD format.") from exc


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a database-backed two-team scouting report using descriptive "
            "statistics, empirical pitch probabilities, batter weaknesses, and "
            "historical pitch-sequence frequencies."
        )
    )
    parser.add_argument("--our-team", required=True)
    parser.add_argument("--opponent-team", required=True)
    parser.add_argument("--our-pitcher", required=True)
    parser.add_argument("--opposing-pitcher", required=True)
    parser.add_argument("--our-lineup", required=True, type=comma_separated_names)
    parser.add_argument("--opponent-lineup", required=True, type=comma_separated_names)
    parser.add_argument("--start-date", required=True, type=iso_date)
    parser.add_argument("--end-date", required=True, type=iso_date)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/statistical_scouting_report.html"),
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        default=None,
        help="Optional PDF output path. Requires WeasyPrint.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if arguments.start_date > arguments.end_date:
        print("Report generation failed: --start-date must be before --end-date.")
        return 2

    try:
        report = build_statistical_report(
            get_engine(),
            our_team=arguments.our_team,
            opponent_team=arguments.opponent_team,
            our_pitcher_name=arguments.our_pitcher,
            opposing_pitcher_name=arguments.opposing_pitcher,
            our_lineup_names=arguments.our_lineup,
            opponent_lineup_names=arguments.opponent_lineup,
            start_date=arguments.start_date,
            end_date=arguments.end_date,
        )
        output_path = render_statistical_scouting_report(
            output_path=arguments.output,
            report_data=report,
        )
        pdf_path = None
        if arguments.pdf_output is not None:
            pdf_path = render_pdf_from_html(
                html_path=output_path,
                pdf_path=arguments.pdf_output,
            )
    except (PlayerLookupError, ValueError, RuntimeError) as exc:
        print(f"Report generation failed: {exc}")
        return 1
    except Exception as exc:
        print(f"Unexpected report generation error: {exc}")
        return 1

    print(f"Statistical scouting report created: {output_path.resolve()}")
    if pdf_path is not None:
        print(f"PDF scouting report created: {pdf_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
