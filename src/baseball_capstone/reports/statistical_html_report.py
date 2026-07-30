"""Render the database-backed statistical scouting HTML report."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATE_DIRECTORY = Path(__file__).resolve().parent / "templates"


def _format_number(value: Any, decimals: int = 1, fallback: str = "—") -> str:
    if value is None:
        return fallback
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return fallback


def _format_pct(value: Any, decimals: int = 1, fallback: str = "—") -> str:
    if value is None:
        return fallback
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return fallback


def _format_rate(value: Any, decimals: int = 3, fallback: str = "—") -> str:
    if value is None:
        return fallback
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return fallback


def get_environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIRECTORY)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters["number"] = _format_number
    environment.filters["pct"] = _format_pct
    environment.filters["rate"] = _format_rate
    return environment


def render_statistical_scouting_report(
    *,
    output_path: Path,
    report_data: dict[str, Any],
) -> Path:
    template = get_environment().get_template("statistical_scouting_report.html")
    data = dict(report_data)
    data.setdefault(
        "generated_at",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.render(**data), encoding="utf-8")
    return output_path


def render_pdf_from_html(*, html_path: Path, pdf_path: Path) -> Path:
    """Render the generated HTML to PDF when WeasyPrint is installed."""
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError(
            "PDF export requires WeasyPrint. Install it with: pip install weasyprint"
        ) from exc
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=str(html_path), base_url=str(html_path.parent)).write_pdf(str(pdf_path))
    return pdf_path
