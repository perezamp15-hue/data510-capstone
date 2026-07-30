"""Run the MLB park collector."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.collectors.parks import collect_parks


def configure_logging(verbose: bool = False) -> None:
    """Configure command-line logging."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Collect MLB parks into PostgreSQL."
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )

    return parser.parse_args()


def main() -> int:
    """Run park collection."""
    arguments = parse_arguments()
    configure_logging(arguments.verbose)

    try:
        metrics = collect_parks()
    except Exception as exc:
        logging.exception("Park collection failed: %s", exc)
        return 1

    print()
    print("MLB park collection succeeded")
    print(f"Team records read: {metrics.records_read}")
    print(f"Parks inserted:    {metrics.records_inserted}")
    print(f"Parks updated:     {metrics.records_updated}")
    print(f"Records rejected:  {metrics.records_rejected}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())