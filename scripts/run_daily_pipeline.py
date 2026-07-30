"""Run the daily MLB data collection pipeline."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from baseball_capstone.features.pitch_sequences import (
    build_pitch_sequence_features,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.collectors.games import collect_games
from baseball_capstone.collectors.parks import collect_parks
from baseball_capstone.collectors.pitches import collect_pitches
from baseball_capstone.collectors.players import collect_players
from baseball_capstone.collectors.teams import collect_teams
from baseball_capstone.collectors.run_tracking import CollectionMetrics

feature_result = run_collector_step(
    "pitch-sequence-features",
    build_pitch_sequence_features,
    start_date=pitch_start_date,
    end_date=target_date,
)
results.append(feature_result)

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineStepResult:
    """Summary of one pipeline stage."""

    name: str
    succeeded: bool
    duration_seconds: float
    metrics: CollectionMetrics | None = None
    error: str | None = None


def configure_logging(verbose: bool = False) -> None:
    """Configure pipeline logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def run_collector_step(
    name: str,
    collector,
    **kwargs,
) -> PipelineStepResult:
    """Run one collector and return a structured result."""
    LOGGER.info("Starting pipeline stage: %s", name)

    started_at = perf_counter()

    try:
        metrics = collector(**kwargs)
    except Exception as exc:
        duration = perf_counter() - started_at

        LOGGER.exception(
            "Pipeline stage failed: %s",
            name,
        )

        return PipelineStepResult(
            name=name,
            succeeded=False,
            duration_seconds=duration,
            error=str(exc),
        )

    duration = perf_counter() - started_at

    LOGGER.info(
        "Pipeline stage completed: %s in %.2f seconds",
        name,
        duration,
    )

    return PipelineStepResult(
        name=name,
        succeeded=True,
        duration_seconds=duration,
        metrics=metrics,
    )


def run_validation_script(script_name: str) -> PipelineStepResult:
    """Run one existing validation script."""
    script_path = PROJECT_ROOT / "scripts" / script_name

    started_at = perf_counter()

    try:
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception as exc:
        return PipelineStepResult(
            name=script_name,
            succeeded=False,
            duration_seconds=perf_counter() - started_at,
            error=str(exc),
        )

    duration = perf_counter() - started_at

    if completed.stdout:
        LOGGER.info(
            "%s output:\n%s",
            script_name,
            completed.stdout.strip(),
        )

    if completed.stderr:
        LOGGER.warning(
            "%s error output:\n%s",
            script_name,
            completed.stderr.strip(),
        )

    return PipelineStepResult(
        name=script_name,
        succeeded=completed.returncode == 0,
        duration_seconds=duration,
        error=(
            None
            if completed.returncode == 0
            else (
                completed.stderr.strip()
                or completed.stdout.strip()
                or f"Exited with code {completed.returncode}"
            )
        ),
    )


def print_pipeline_summary(
    results: list[PipelineStepResult],
) -> None:
    """Print a concise pipeline summary."""
    print()
    print("=" * 72)
    print("DAILY MLB PIPELINE SUMMARY")
    print("=" * 72)

    for result in results:
        status = "SUCCESS" if result.succeeded else "FAILED"

        print(
            f"{result.name:<28} "
            f"{status:<8} "
            f"{result.duration_seconds:>8.2f}s"
        )

        if result.metrics is not None:
            print(
                "  "
                f"read={result.metrics.records_read}, "
                f"inserted={result.metrics.records_inserted}, "
                f"updated={result.metrics.records_updated}, "
                f"rejected={result.metrics.records_rejected}"
            )

        if result.error:
            print(f"  error={result.error}")

    print("=" * 72)


def parse_arguments() -> argparse.Namespace:
    """Parse pipeline command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the daily MLB data pipeline."
    )

    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help=(
            "Pipeline target date in YYYY-MM-DD format. "
            "Defaults to today."
        ),
    )

    parser.add_argument(
        "--schedule-days-back",
        type=int,
        default=2,
        help=(
            "Number of days before the target date to refresh "
            "schedule records. Default: 2."
        ),
    )

    parser.add_argument(
        "--pitch-days-back",
        type=int,
        default=2,
        help=(
            "Number of days before the target date to search "
            "for uncollected final games. Default: 2."
        ),
    )

    parser.add_argument(
        "--pitch-limit",
        type=int,
        default=10,
        help=(
            "Maximum games processed by the pitch stage. "
            "Default: 10."
        ),
    )

    parser.add_argument(
        "--skip-players",
        action="store_true",
        help="Skip the active roster and player refresh.",
    )

    parser.add_argument(
        "--skip-pitches",
        action="store_true",
        help="Skip pitch-by-pitch collection.",
    )

    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip post-pipeline validation scripts.",
    )

    parser.add_argument(
        "--force-pitches",
        action="store_true",
        help="Recheck games already marked as collected.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )

    return parser.parse_args()


def main() -> int:
    """Run the daily pipeline."""
    arguments = parse_arguments()
    configure_logging(arguments.verbose)

    target_date = arguments.date or date.today()

    if arguments.schedule_days_back < 0:
        raise ValueError(
            "--schedule-days-back cannot be negative."
        )

    if arguments.pitch_days_back < 0:
        raise ValueError(
            "--pitch-days-back cannot be negative."
        )

    if arguments.pitch_limit is not None and arguments.pitch_limit < 1:
        raise ValueError(
            "--pitch-limit must be at least 1."
        )

    schedule_start_date = target_date - timedelta(
        days=arguments.schedule_days_back
    )

    pitch_start_date = target_date - timedelta(
        days=arguments.pitch_days_back
    )

    results: list[PipelineStepResult] = []

    # Teams are required by every later stage.
    team_result = run_collector_step(
        "teams",
        collect_teams,
    )
    results.append(team_result)

    if not team_result.succeeded:
        print_pipeline_summary(results)
        return 1

    # Parks require teams.
    park_result = run_collector_step(
        "parks",
        collect_parks,
    )
    results.append(park_result)

    if not park_result.succeeded:
        print_pipeline_summary(results)
        return 1

    # Players require teams but are not required every single run.
    if not arguments.skip_players:
        player_result = run_collector_step(
            "players",
            collect_players,
        )
        results.append(player_result)

        if not player_result.succeeded:
            print_pipeline_summary(results)
            return 1

    # Schedule refresh is required before pitch collection.
    game_result = run_collector_step(
        "games",
        collect_games,
        start_date=schedule_start_date,
        end_date=target_date,
    )
    results.append(game_result)

    if not game_result.succeeded:
        print_pipeline_summary(results)
        return 1

    if not arguments.skip_pitches:
        pitch_result = run_collector_step(
            "pitches",
            collect_pitches,
            start_date=pitch_start_date,
            end_date=target_date,
            force=arguments.force_pitches,
            replace=False,
            limit=arguments.pitch_limit,
        )
        results.append(pitch_result)

    if not arguments.skip_validation:
        validation_scripts = [
            "check_database.py",
            "check_schema.py",
            "check_teams.py",
            "check_parks.py",
            "check_players.py",
            "check_games.py",
        ]

        if not arguments.skip_pitches:
            validation_scripts.append("check_pitches.py")

        for script_name in validation_scripts:
            validation_result = run_validation_script(
                script_name
            )
            results.append(validation_result)

    print_pipeline_summary(results)

    failed_steps = [
        result
        for result in results
        if not result.succeeded
    ]

    return 1 if failed_steps else 0


if __name__ == "__main__":
    raise SystemExit(main())