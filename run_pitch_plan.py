"""Generate the HTML pitcher-versus-lineup game plan.

Running this file with no arguments creates the built-in Tarik Skubal vs.
Los Angeles Dodgers matchup. Player names are resolved from the ``players``
table, so the command does not require memorizing MLB player IDs.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from analytics.game_plan_repository import GamePlanRepository
from analytics.game_plan_service import GamePlanService
from reports.html_report import write_html_report


# This is a configurable matchup preset, not a claim that it is today's
# officially posted batting order. Change the order here whenever needed.
SKUBAL_VS_DODGERS = {
    "pitcher": "Tarik Skubal",
    "opponent_team": "Los Angeles Dodgers",
    "season": 2026,
    "lineup": [
        "Shohei Ohtani",
        "Andy Pages",
        "Freddie Freeman",
        "Mookie Betts",
        "Max Muncy",
        "Kyle Tucker",
        "Teoscar Hernández",
        "Dalton Rushing",
        "Tommy Edman",
    ],
    "output": "output/tarik_skubal_vs_los_angeles_dodgers.html",
}


def parse_id_lineup(value: str | None) -> list[int] | None:
    """Parse comma-separated numeric player IDs."""
    if not value:
        return None
    try:
        values = [int(part.strip()) for part in value.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--lineup-ids must contain only comma-separated integers."
        ) from exc
    return values or None


def parse_name_lineup(value: str | None) -> list[str] | None:
    """Parse comma-separated player names."""
    if not value:
        return None
    names = [" ".join(part.strip().split()) for part in value.split(",")]
    return [name for name in names if name] or None


def safe_filename(value: str) -> str:
    """Convert a report title into a portable filename."""
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value or "game_plan"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create one HTML pitcher-versus-lineup report. With no arguments, "
            "the Tarik Skubal vs. Dodgers preset is used."
        )
    )
    parser.add_argument(
        "--preset",
        choices=["skubal-vs-dodgers", "none"],
        default=None,
        help="Use the built-in matchup preset. No arguments defaults to skubal-vs-dodgers.",
    )
    pitcher = parser.add_mutually_exclusive_group()
    pitcher.add_argument("--pitcher-id", type=int)
    pitcher.add_argument("--pitcher", help="Pitcher full name, such as 'Tarik Skubal'")

    team = parser.add_mutually_exclusive_group()
    team.add_argument("--opponent-team-id", type=int)
    team.add_argument("--team", help="Opponent name or abbreviation, such as 'Dodgers' or 'LAD'")

    lineup = parser.add_mutually_exclusive_group()
    lineup.add_argument("--lineup-ids", type=parse_id_lineup, help="Comma-separated batter IDs")
    lineup.add_argument(
        "--lineup",
        type=parse_name_lineup,
        help='Comma-separated names in batting order, e.g. "Shohei Ohtani,Mookie Betts,..."',
    )

    parser.add_argument("--game-pk", type=int, help="Load the stored starting lineup for a game")
    parser.add_argument("--season", type=int)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--use-ml", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--skip-roster-validation", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def resolve_arguments(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict:
    """Resolve names to IDs and return inputs accepted by GamePlanService."""
    repository = GamePlanRepository()

    no_matchup_arguments = not any(
        [
            args.pitcher_id,
            args.pitcher,
            args.opponent_team_id,
            args.team,
            args.lineup_ids,
            args.lineup,
            args.game_pk,
        ]
    )
    use_preset = args.preset == "skubal-vs-dodgers" or (
        args.preset is None and no_matchup_arguments
    )

    if use_preset:
        pitcher_name = SKUBAL_VS_DODGERS["pitcher"]
        team_name = SKUBAL_VS_DODGERS["opponent_team"]
        lineup_names = list(SKUBAL_VS_DODGERS["lineup"])
        season = args.season or int(SKUBAL_VS_DODGERS["season"])
        output = args.output or Path(str(SKUBAL_VS_DODGERS["output"]))
    else:
        pitcher_name = args.pitcher
        team_name = args.team
        lineup_names = args.lineup
        season = args.season
        output = args.output

    pitcher_id = args.pitcher_id
    pitcher_display_name = pitcher_name or str(pitcher_id or "pitcher")
    if pitcher_id is None:
        if not pitcher_name:
            parser.error("Provide --pitcher-id or --pitcher.")
        pitcher_row = repository.find_player_by_name(pitcher_name)
        pitcher_id = int(pitcher_row["player_id"])
        pitcher_display_name = str(pitcher_row["full_name"])

    opponent_team_id = args.opponent_team_id
    opponent_display_name = team_name or str(opponent_team_id or "opponent")
    if args.game_pk is None and opponent_team_id is None:
        if not team_name:
            parser.error("Provide --opponent-team-id or --team when --game-pk is not used.")
        team_row = repository.find_team_by_name(team_name)
        opponent_team_id = int(team_row["team_id"])
        opponent_display_name = str(team_row["team_name"])

    lineup_ids = args.lineup_ids
    if args.game_pk is None and lineup_ids is None:
        if not lineup_names:
            parser.error("Provide --lineup-ids or --lineup when --game-pk is not used.")
        players = repository.find_players_by_names(
            lineup_names,
            team_id=opponent_team_id,
        )
        lineup_ids = [int(player["player_id"]) for player in players]
        resolved_names = [str(player["full_name"]) for player in players]
        print("Resolved batting order:")
        for slot, (name, player_id) in enumerate(zip(resolved_names, lineup_ids), start=1):
            print(f"  {slot}. {name} ({player_id})")

    if output is None:
        output = Path(
            "output"
        ) / f"{safe_filename(pitcher_display_name)}_vs_{safe_filename(opponent_display_name)}.html"

    return {
        "pitcher_id": int(pitcher_id),
        "game_pk": args.game_pk,
        "opponent_team_id": opponent_team_id,
        "lineup_ids": lineup_ids,
        "season": season,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "use_ml": bool(args.use_ml),
        "validate_rosters": not args.skip_roster_validation,
        "output": output,
    }


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        resolved = resolve_arguments(args, parser)
        output = resolved.pop("output")
        print(
            f"Building report for pitcher_id={resolved['pitcher_id']} "
            f"against team_id={resolved.get('opponent_team_id')}..."
        )
        report = GamePlanService().build_game_plan(**resolved)
        path = write_html_report(report, output)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"HTML report created: {path.resolve()}")
    print(f"Open it with: open {path.resolve()}")


if __name__ == "__main__":
    main()
