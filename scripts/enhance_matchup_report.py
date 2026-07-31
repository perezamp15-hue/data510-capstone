#!/usr/bin/env python3
"""
Enhance an existing matchup HTML report with advanced scouting sections.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from baseball_capstone.analytics.advanced_scouting import (
    AdvancedScoutingRepository,
)

from baseball_capstone.reports.advanced_sections import (
    render_all_sections,
)

def database_url() -> str:
    load_dotenv()
    url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_PUBLIC_URL or DATABASE_URL is required.")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Add advanced scouting sections to a matchup HTML report.")
    p.add_argument("--input", type=Path, required=True, help="Existing matchup HTML file")
    p.add_argument("--output", type=Path, help="Enhanced output HTML; defaults to *_enhanced.html")
    p.add_argument("--pitcher-id", type=int, required=True, help="Pitcher shown in inning/release/heat-map sections")
    p.add_argument("--opponent-team-id", type=int, required=True, help="Team shown in offensive rolling overview")
    p.add_argument("--season", type=int)
    p.add_argument("--start-date")
    p.add_argument("--end-date")
    return p


def inject(html: str, css: str, sections: str) -> str:
    html = re.sub(r'<style id="advanced-scouting-css">.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<!-- ADVANCED_SCOUTING_START -->.*?<!-- ADVANCED_SCOUTING_END -->', '', html, flags=re.S)
    if "</head>" not in html or "</main>" not in html:
        raise ValueError("Input must contain </head> and </main> tags.")
    html = html.replace("</head>", css + "\n</head>", 1)
    nav_links = '<a href="#opponent-overview">Team Trends</a><a href="#pitcher-progression">By Inning</a><a href="#enhanced-heatmaps">Heat Maps</a><a href="#release-points">Release</a>'
    if "</nav>" in html and "#pitcher-progression" not in html:
        html = html.replace("</nav>", nav_links + "</nav>", 1)
    block = f"\n<!-- ADVANCED_SCOUTING_START -->\n{sections}\n<!-- ADVANCED_SCOUTING_END -->\n"
    return html.replace("</main>", block + "</main>", 1)


def main() -> int:
    args = parser().parse_args()
    if not args.input.exists():
        raise FileNotFoundError(args.input)
    output = args.output or args.input.with_name(args.input.stem + "_enhanced.html")
    engine = create_engine(database_url(), pool_pre_ping=True, connect_args={"connect_timeout": 20})
    repository = AdvancedScoutingRepository(engine)

    pitcher_pitches = repository.pitcher_pitches(args.pitcher_id, args.season, args.start_date, args.end_date)
    team_pitches = repository.team_batting_pitches(args.opponent_team_id, args.season, args.start_date, args.end_date)
    if pitcher_pitches.empty:
        raise RuntimeError("No pitcher pitches were returned for the selected filters.")

    sections = render_all_sections(
        pitcher_name=repository.player_name(args.pitcher_id),
        team_name=repository.team_name(args.opponent_team_id),
        inning_rows=build_inning_splits(pitcher_pitches),
        release_rows=build_release_summary(pitcher_pitches),
        heatmaps={
            "frequency": build_heatmap(pitcher_pitches, "frequency"),
            "whiff": build_heatmap(pitcher_pitches, "whiff"),
            "damage": build_heatmap(pitcher_pitches, "damage"),
        },
        team_values=build_team_rolling_offense(team_pitches),
    )
    enhanced = inject(args.input.read_text(encoding="utf-8"), advanced_css(), sections)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(enhanced, encoding="utf-8")
    print(f"Enhanced matchup report created: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
