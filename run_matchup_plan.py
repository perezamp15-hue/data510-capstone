"""Generate one two-sided HTML team matchup plan.

The report contains:
1. Offensive plan: our batting order versus the opposing pitcher.
2. Defensive plan: our pitcher versus the opponent batting order.

The default preset is a configurable Dodgers/Tigers example with Yoshinobu
Yamamoto as the Dodgers pitcher and Tarik Skubal as the Tigers pitcher.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from analytics.game_plan_repository import GamePlanRepository
from analytics.game_plan_service import GamePlanService
from reports.team_matchup_html import write_team_matchup_html


# These are editable example batting orders, not a claim that they are the
# officially posted lineups for a particular game. Change names/order here or
# pass both lineups on the command line.
YAMAMOTO_VS_SKUBAL_PRESET: dict[str, Any] = {
    "our_team": "Los Angeles Dodgers",
    "our_pitcher": "Yoshinobu Yamamoto",
    "our_lineup": [
        "Shohei Ohtani",
        "Mookie Betts",
        "Freddie Freeman",
        "Teoscar Hernández",
        "Max Muncy",
        "Will Smith",
        "Tommy Edman",
        "Andy Pages",
        "Dalton Rushing",
    ],
    "opponent_team": "Detroit Tigers",
    "opposing_pitcher": "Tarik Skubal",
    "opponent_lineup": [
        "Gleyber Torres",
        "Kerry Carpenter",
        "Riley Greene",
        "Spencer Torkelson",
        "Colt Keith",
        "Wenceel Pérez",
        "Parker Meadows",
        "Dillon Dingler",
        "Javier Báez",
    ],
    "season": 2026,
    "output": "output/dodgers_vs_tigers_yamamoto_skubal.html",
}


def parse_lineup(value: str | None) -> list[str] | None:
    """Parse a comma-separated lineup containing names and/or player IDs."""
    if not value:
        return None
    entries = [" ".join(part.strip().split()) for part in value.split(",")]
    return [entry for entry in entries if entry] or None


def safe_filename(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return value or "team_matchup"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create one HTML team matchup report with an offensive plan "
            "against the opposing pitcher and a defensive plan for our pitcher."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Example for any matchup:\n"
            "  python3 run_matchup_plan.py --our-team \"Philadelphia Phillies\" "
            "--our-pitcher \"Zack Wheeler\" --our-lineup \"PLAYER1,...,PLAYER9\" "
            "--opponent-team \"Atlanta Braves\" --opposing-pitcher \"Spencer Strider\" "
            "--opponent-lineup \"PLAYER1,...,PLAYER9\" --season 2026"
        ),
    )
    parser.add_argument(
        "--preset",
        choices=["yamamoto-vs-skubal", "none"],
        default=None,
        help="No matchup arguments defaults to the configurable Yamamoto/Skubal preset.",
    )

    parser.add_argument("--our-team", help="Our team name or abbreviation")
    parser.add_argument("--our-team-id", type=int)
    parser.add_argument("--our-pitcher", help="Our starting pitcher name")
    parser.add_argument("--our-pitcher-id", type=int)
    parser.add_argument(
        "--our-lineup",
        type=parse_lineup,
        help="Our batting order as comma-separated names/IDs",
    )

    parser.add_argument("--opponent-team", help="Opponent team name or abbreviation")
    parser.add_argument("--opponent-team-id", type=int)
    parser.add_argument("--opposing-pitcher", help="Opponent starting pitcher name")
    parser.add_argument("--opposing-pitcher-id", type=int)
    parser.add_argument(
        "--opponent-lineup",
        type=parse_lineup,
        help="Opponent batting order as comma-separated names/IDs",
    )

    parser.add_argument("--season", type=int)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument(
        "--use-ml",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the existing pitch-tendency classifier; no new ML is added.",
    )
    parser.add_argument("--skip-roster-validation", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser


def _resolve_team(
    repository: GamePlanRepository,
    team_id: int | None,
    team_name: str | None,
    label: str,
    validate_roster: bool = True,
) -> dict[str, Any]:
    if team_id is not None:
        row = repository.get_team_metadata(int(team_id))
        if not row:
            raise ValueError(f"No {label} was found for team ID {team_id}.")
        row = dict(row)
        row.setdefault("team_id", int(team_id))
        return row
    if not team_name:
        raise ValueError(f"Provide --{label.replace('_', '-')} or --{label.replace('_', '-')}-id.")
    return repository.find_team_by_name(team_name)


def _resolve_player(
    repository: GamePlanRepository,
    player_id: int | None,
    player_name: str | None,
    team_id: int,
    label: str,
    validate_roster: bool = True,
) -> dict[str, Any]:
    if player_id is not None:
        row = repository.find_player_by_id(int(player_id))
    else:
        if not player_name:
            raise ValueError(f"Provide --{label.replace('_', '-')} or --{label.replace('_', '-')}-id.")
        row = repository.find_player_by_name(player_name, team_id=team_id)
    actual_team = row.get("current_team_id")
    if validate_roster and actual_team is not None and int(actual_team) != int(team_id):
        raise ValueError(
            f"{row.get('full_name')} is listed with {row.get('team_name') or 'another team'}, "
            f"not selected team ID {team_id}. Use --skip-roster-validation for a historical setup."
        )
    return row


def _resolve_lineup(
    repository: GamePlanRepository,
    values: list[str] | None,
    team_id: int,
    label: str,
) -> list[dict[str, Any]]:
    if not values:
        raise ValueError(f"Provide --{label.replace('_', '-')} with the batting order.")
    players = repository.find_players_by_names(values, team_id=team_id)
    if len(players) != 9:
        raise ValueError(f"{label.replace('_', ' ').title()} must contain exactly 9 players; received {len(players)}.")
    return players


def resolve_arguments(args: argparse.Namespace) -> dict[str, Any]:
    repository = GamePlanRepository()
    no_matchup_args = not any(
        [
            args.our_team,
            args.our_team_id,
            args.our_pitcher,
            args.our_pitcher_id,
            args.our_lineup,
            args.opponent_team,
            args.opponent_team_id,
            args.opposing_pitcher,
            args.opposing_pitcher_id,
            args.opponent_lineup,
        ]
    )
    use_preset = args.preset == "yamamoto-vs-skubal" or (
        args.preset is None and no_matchup_args
    )

    if use_preset:
        cfg = dict(YAMAMOTO_VS_SKUBAL_PRESET)
        our_team_name = cfg["our_team"]
        our_pitcher_name = cfg["our_pitcher"]
        our_lineup_values = list(cfg["our_lineup"])
        opponent_team_name = cfg["opponent_team"]
        opposing_pitcher_name = cfg["opposing_pitcher"]
        opponent_lineup_values = list(cfg["opponent_lineup"])
        season = args.season or int(cfg["season"])
        output = args.output or Path(str(cfg["output"]))
    else:
        our_team_name = args.our_team
        our_pitcher_name = args.our_pitcher
        our_lineup_values = args.our_lineup
        opponent_team_name = args.opponent_team
        opposing_pitcher_name = args.opposing_pitcher
        opponent_lineup_values = args.opponent_lineup
        season = args.season
        output = args.output

    our_team = _resolve_team(repository, args.our_team_id, our_team_name, "our_team")
    opponent_team = _resolve_team(
        repository, args.opponent_team_id, opponent_team_name, "opponent_team"
    )
    our_team_id = int(our_team["team_id"])
    opponent_team_id = int(opponent_team["team_id"])

    # For historical/custom reports, name resolution still prefers the selected
    # team; roster validation can be disabled at service execution time.
    our_pitcher = _resolve_player(
        repository,
        args.our_pitcher_id,
        our_pitcher_name,
        our_team_id,
        "our_pitcher",
        validate_roster=not args.skip_roster_validation,
    )
    opposing_pitcher = _resolve_player(
        repository,
        args.opposing_pitcher_id,
        opposing_pitcher_name,
        opponent_team_id,
        "opposing_pitcher",
        validate_roster=not args.skip_roster_validation,
    )
    our_lineup = _resolve_lineup(repository, our_lineup_values, our_team_id, "our_lineup")
    opponent_lineup = _resolve_lineup(
        repository, opponent_lineup_values, opponent_team_id, "opponent_lineup"
    )

    if output is None:
        output = Path("output") / (
            f"{safe_filename(str(our_team.get('team_name', 'our_team')))}_vs_"
            f"{safe_filename(str(opponent_team.get('team_name', 'opponent')))}.html"
        )

    return {
        "our_team": our_team,
        "opponent_team": opponent_team,
        "our_pitcher": our_pitcher,
        "opposing_pitcher": opposing_pitcher,
        "our_lineup": our_lineup,
        "opponent_lineup": opponent_lineup,
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
        resolved = resolve_arguments(args)
        output = resolved.pop("output")
        service = GamePlanService()

        our_team_id = int(resolved["our_team"]["team_id"])
        opponent_team_id = int(resolved["opponent_team"]["team_id"])
        our_pitcher_id = int(resolved["our_pitcher"]["player_id"])
        opposing_pitcher_id = int(resolved["opposing_pitcher"]["player_id"])
        our_lineup_ids = [int(p["player_id"]) for p in resolved["our_lineup"]]
        opponent_lineup_ids = [int(p["player_id"]) for p in resolved["opponent_lineup"]]

        print(
            f"Building offensive plan: {resolved['our_team']['team_name']} hitters "
            f"vs. {resolved['opposing_pitcher']['full_name']}..."
        )
        offensive_report = service.build_game_plan(
            pitcher_id=opposing_pitcher_id,
            pitcher_team_id=opponent_team_id,
            opponent_team_id=our_team_id,
            lineup_ids=our_lineup_ids,
            season=resolved["season"],
            start_date=resolved["start_date"],
            end_date=resolved["end_date"],
            use_ml=resolved["use_ml"],
            validate_rosters=resolved["validate_rosters"],
        )

        print(
            f"Building defensive plan: {resolved['our_pitcher']['full_name']} "
            f"vs. {resolved['opponent_team']['team_name']} hitters..."
        )
        defensive_report = service.build_game_plan(
            pitcher_id=our_pitcher_id,
            pitcher_team_id=our_team_id,
            opponent_team_id=opponent_team_id,
            lineup_ids=opponent_lineup_ids,
            season=resolved["season"],
            start_date=resolved["start_date"],
            end_date=resolved["end_date"],
            opposing_pitcher_id=opposing_pitcher_id,
            use_ml=resolved["use_ml"],
            validate_rosters=resolved["validate_rosters"],
        )

        matchup = {
            **resolved,
            "offensive_report": offensive_report,
            "defensive_report": defensive_report,
        }
        path = write_team_matchup_html(matchup, output)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"HTML team matchup report created: {path.resolve()}")
    print(f"Open it with: open {path.resolve()}")


if __name__ == "__main__":
    main()
