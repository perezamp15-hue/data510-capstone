"""Refresh MLB teams, parks, and active rosters."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))


from baseball_capstone.collectors.parks import collect_parks
from baseball_capstone.collectors.players import collect_players
from baseball_capstone.collectors.teams import collect_teams


def main() -> int:
    """Run the roster dependency pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
    )

    try:
        team_metrics = collect_teams()
        park_metrics = collect_parks()
        player_metrics = collect_players()
    except Exception as exc:
        logging.exception(
            "Roster pipeline failed: %s",
            exc,
        )
        return 1

    print()
    print("Roster pipeline succeeded")
    print(
        f"Teams: read={team_metrics.records_read}, "
        f"inserted={team_metrics.records_inserted}, "
        f"updated={team_metrics.records_updated}"
    )
    print(
        f"Parks: read={park_metrics.records_read}, "
        f"inserted={park_metrics.records_inserted}, "
        f"updated={park_metrics.records_updated}"
    )
    print(
        f"Players: read={player_metrics.records_read}, "
        f"inserted={player_metrics.records_inserted}, "
        f"updated={player_metrics.records_updated}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())