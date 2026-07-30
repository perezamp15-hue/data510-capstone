from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta

from analytics.database import dispose_engine, test_database_connection
from scripts import scrape_game_feed, scrape_statcast, scrape_transactions

logging.basicConfig(
    level=os.getenv("ANALYTICS_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("daily_pipeline")


def valid_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD format.") from exc


def run_pipeline_for_date(target_date: str, run_analytics: bool = True) -> int:
    failures: list[str] = []
    logger.info("Starting pipeline for %s", target_date)

    try:
        metadata = test_database_connection()
        logger.info("Connected to database %s", metadata["database_name"])
    except Exception:
        logger.exception("Database preflight failed")
        return 2

    phases = [
        ("game feed", lambda: scrape_game_feed.run(target_date), True),
        ("statcast", lambda: scrape_statcast.run(target_date, target_date), False),
        ("transactions", lambda: scrape_transactions.run(target_date), False),
    ]

    for name, action, required in phases:
        try:
            logger.info("Running %s phase", name)
            action()
            logger.info("Completed %s phase", name)
        except Exception:
            logger.exception("%s phase failed", name)
            failures.append(name)
            if required:
                break

    if run_analytics and not failures:
        try:
            from analytics.run_phase_one import run_phase_one
            run_phase_one()
        except Exception:
            logger.exception("Analytics validation failed")
            failures.append("analytics")

    dispose_engine()
    if failures:
        logger.error("Pipeline completed with failures: %s", ", ".join(failures))
        return 1

    logger.info("Pipeline completed successfully for %s", target_date)
    return 0


def build_parser() -> argparse.ArgumentParser:
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    parser = argparse.ArgumentParser(description="Run the MLB warehouse daily pipeline.")
    parser.add_argument("date", nargs="?", default=yesterday, type=valid_date)
    parser.add_argument("--skip-analytics", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check_only:
        print(test_database_connection())
        dispose_engine()
        return 0
    env_enabled = os.getenv("PIPELINE_RUN_ANALYTICS", "true").lower() in {"1", "true", "yes"}
    return run_pipeline_for_date(args.date, run_analytics=env_enabled and not args.skip_analytics)


if __name__ == "__main__":
    sys.exit(main())
