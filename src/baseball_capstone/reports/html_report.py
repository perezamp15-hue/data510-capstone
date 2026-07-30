"""Render self-contained pitch-sequence HTML reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATE_DIRECTORY = Path(__file__).resolve().parent / "templates"


def get_template_environment() -> Environment:
    """Create the Jinja template environment."""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIRECTORY)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
        ),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_pitch_sequence_report(
    *,
    output_path: Path,
    report_data: dict[str, Any],
) -> Path:
    """Render a self-contained HTML report."""
    environment = get_template_environment()

    template = environment.get_template(
        "pitch_sequence_report.html"
    )

    template_data = dict(report_data)

    template_data.setdefault(
        "generated_at",
        datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
    )

    rendered_html = template.render(**template_data)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        rendered_html,
        encoding="utf-8",
    )

    return output_path

def render_two_team_game_plan(
    *,
    output_path: Path,
    report_data: dict[str, Any],
) -> Path:
    """Render a complete two-team strategy report."""
    environment = get_template_environment()

    template = environment.get_template(
        "two_team_game_plan.html"
    )

    template_data = dict(report_data)

    template_data.setdefault(
        "generated_at",
        datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
    )

    rendered_html = template.render(**template_data)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        rendered_html,
        encoding="utf-8",
    )

    return output_path