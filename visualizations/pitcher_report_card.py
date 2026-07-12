from __future__ import annotations
import math
from pathlib import Path
from typing import Any
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch

# CONFIGURATION
PAGE_BACKGROUND = "#0B1220"
PANEL_BACKGROUND = "#111B2E"
PANEL_SECONDARY = "#17233A"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#AAB6C8"
GRID_COLOR = "#334155"
ACCENT_COLOR = "#38BDF8"

GRADE_COLORS = {
    "elite": "#22C55E",
    "plus": "#4ADE80",
    "above_average": "#84CC16",
    "average": "#EAB308",
    "fringe": "#F59E0B",
    "below_average": "#F97316",
    "poor": "#EF4444",
}

PITCH_COLORS = {
    "FF": "#EF4444",
    "FA": "#EF4444",
    "SI": "#F97316",
    "FC": "#FB923C",
    "SL": "#3B82F6",
    "ST": "#8B5CF6",
    "CU": "#06B6D4",
    "KC": "#14B8A6",
    "CH": "#22C55E",
    "FS": "#84CC16",
    "FO": "#A3E635",
    "SV": "#6366F1",
    "KN": "#EC4899",
}

DEFAULT_PITCH_COLOR = "#94A3B8"

# GENERAL HELPERS
def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default

        numeric = float(value)

        if math.isnan(numeric):
            return default

        return numeric

    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def shorten_text(
    text: str | None,
    maximum_length: int,
) -> str:
    if not text:
        return ""

    if len(text) <= maximum_length:
        return text

    return text[: maximum_length - 3].rstrip() + "..."


def wrap_text(
    text: str | None,
    line_length: int = 75,
) -> str:
    if not text:
        return ""

    words = text.split()
    lines: list[str] = []
    current_line: list[str] = []
    current_length = 0

    for word in words:
        proposed_length = (
            current_length
            + len(word)
            + (
                1
                if current_line
                else 0
            )
        )

        if (
            proposed_length > line_length
            and current_line
        ):
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)

        else:
            current_line.append(word)
            current_length = proposed_length

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(lines)


def get_pitch_color(
    pitch_type: str | None,
) -> str:
    if not pitch_type:
        return DEFAULT_PITCH_COLOR

    return PITCH_COLORS.get(
        pitch_type,
        DEFAULT_PITCH_COLOR,
    )


def get_grade_color(
    color_group: str | None,
) -> str:
    if not color_group:
        return GRADE_COLORS["average"]

    return GRADE_COLORS.get(
        color_group,
        GRADE_COLORS["average"],
    )


def remove_axis_decoration(
    axis: Axes,
) -> None:
    axis.set_xticks([])
    axis.set_yticks([])

    for spine in axis.spines.values():
        spine.set_visible(False)


def add_panel(
    axis: Axes,
    background: str = PANEL_BACKGROUND,
    radius: float = 0.025,
) -> None:
    axis.set_facecolor("none")

    panel = FancyBboxPatch(
        (0, 0),
        1,
        1,
        transform=axis.transAxes,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=0,
        facecolor=background,
        clip_on=False,
        zorder=-10,
    )

    axis.add_patch(panel)


def add_section_title(
    axis: Axes,
    title: str,
    x: float = 0.04,
    y: float = 0.92,
    fontsize: float = 13,
) -> None:
    axis.text(
        x,
        y,
        title.upper(),
        transform=axis.transAxes,
        color=TEXT_PRIMARY,
        fontsize=fontsize,
        fontweight="bold",
        ha="left",
        va="top",
    )

# HEADER
def draw_header(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)

    header = report.get("header", {})
    overall_grade = report.get("overall_grade") or {}

    pitcher_name = header.get(
        "pitcher_name",
        "Unknown Pitcher",
    )

    subtitle_parts = []

    if header.get("throws_display"):
        subtitle_parts.append(
            header["throws_display"]
        )

    if header.get("season"):
        subtitle_parts.append(
            str(header["season"])
        )

    subtitle = "  •  ".join(subtitle_parts)

    pitcher_type = header.get("pitcher_type") or ""

    axis.text(
        0.02,
        0.78,
        pitcher_name,
        transform=axis.transAxes,
        color=TEXT_PRIMARY,
        fontsize=28,
        fontweight="bold",
        ha="left",
        va="center",
    )

    axis.text(
        0.02,
        0.49,
        subtitle,
        transform=axis.transAxes,
        color=TEXT_SECONDARY,
        fontsize=12,
        ha="left",
        va="center",
    )

    axis.text(
        0.02,
        0.21,
        shorten_text(
            pitcher_type,
            110,
        ),
        transform=axis.transAxes,
        color=ACCENT_COLOR,
        fontsize=11,
        fontweight="semibold",
        ha="left",
        va="center",
    )

    grade = safe_int(
        overall_grade.get("grade"),
        default=50,
    )

    grade_label = overall_grade.get(
        "label",
        "Average",
    )

    color_group = overall_grade.get(
        "color_group",
        "average",
    )

    grade_color = get_grade_color(color_group)

    grade_box = FancyBboxPatch(
        (0.84, 0.13),
        0.14,
        0.74,
        transform=axis.transAxes,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=2,
        edgecolor=grade_color,
        facecolor=PANEL_BACKGROUND,
    )

    axis.add_patch(grade_box)

    axis.text(
        0.91,
        0.62,
        str(grade),
        transform=axis.transAxes,
        color=grade_color,
        fontsize=32,
        fontweight="bold",
        ha="center",
        va="center",
    )

    axis.text(
        0.91,
        0.36,
        "OVERALL",
        transform=axis.transAxes,
        color=TEXT_SECONDARY,
        fontsize=8,
        fontweight="bold",
        ha="center",
        va="center",
    )

    axis.text(
        0.91,
        0.21,
        grade_label,
        transform=axis.transAxes,
        color=TEXT_PRIMARY,
        fontsize=8,
        ha="center",
        va="center",
    )

# GRADE CARDS
def draw_grade_cards(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)
    add_panel(axis)
    add_section_title(axis, "Scouting Grades")

    grade_cards = [
        grade
        for grade in report.get(
            "grade_cards",
            [],
        )
        if not grade.get("is_overall")
    ]

    if not grade_cards:
        axis.text(
            0.5,
            0.5,
            "No grade data available",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            ha="center",
            va="center",
        )
        return

    card_width = 0.17
    gap = 0.022
    starting_x = 0.04
    card_y = 0.16
    card_height = 0.58

    for index, grade_card in enumerate(
        grade_cards[:5]
    ):
        x_position = (
            starting_x
            + index
            * (
                card_width
                + gap
            )
        )

        grade = safe_int(
            grade_card.get("grade"),
            default=50,
        )

        grade_color = get_grade_color(
            grade_card.get("color_group")
        )

        card = FancyBboxPatch(
            (
                x_position,
                card_y,
            ),
            card_width,
            card_height,
            transform=axis.transAxes,
            boxstyle=(
                "round,pad=0.012,"
                "rounding_size=0.025"
            ),
            linewidth=1.5,
            edgecolor=grade_color,
            facecolor=PANEL_SECONDARY,
        )

        axis.add_patch(card)

        axis.text(
            x_position + card_width / 2,
            card_y + 0.37,
            str(grade),
            transform=axis.transAxes,
            color=grade_color,
            fontsize=24,
            fontweight="bold",
            ha="center",
            va="center",
        )

        axis.text(
            x_position + card_width / 2,
            card_y + 0.18,
            grade_card.get(
                "name",
                "",
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            fontweight="bold",
            ha="center",
            va="center",
        )

        axis.text(
            x_position + card_width / 2,
            card_y + 0.07,
            grade_card.get(
                "label",
                "",
            ),
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            fontsize=7,
            ha="center",
            va="center",
        )

# RADAR CHART
def draw_radar_chart(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    radar_data = report.get(
        "radar_chart",
        {},
    )

    labels = radar_data.get(
        "labels",
        [],
    )

    values = radar_data.get(
        "values",
        [],
    )

    if not labels or not values:
        axis.text(
            0.5,
            0.5,
            "No radar data available",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            ha="center",
            va="center",
        )
        return

    values = [
        safe_float(value, 50)
        for value in values
    ]

    angles = np.linspace(
        0,
        2 * np.pi,
        len(labels),
        endpoint=False,
    ).tolist()

    closed_values = values + values[:1]
    closed_angles = angles + angles[:1]

    axis.set_facecolor(PANEL_BACKGROUND)

    axis.set_theta_offset(
        np.pi / 2
    )

    axis.set_theta_direction(-1)

    axis.set_xticks(angles)

    axis.set_xticklabels(
        labels,
        color=TEXT_PRIMARY,
        fontsize=8,
    )

    axis.set_ylim(20, 80)

    axis.set_yticks(
        [20, 30, 40, 50, 60, 70, 80]
    )

    axis.set_yticklabels(
        [
            "20",
            "",
            "40",
            "50",
            "60",
            "",
            "80",
        ],
        color=TEXT_SECONDARY,
        fontsize=7,
    )

    axis.grid(
        color=GRID_COLOR,
        linewidth=0.8,
        alpha=0.8,
    )

    axis.spines["polar"].set_color(
        GRID_COLOR
    )

    axis.plot(
        closed_angles,
        closed_values,
        color=ACCENT_COLOR,
        linewidth=2.5,
    )

    axis.fill(
        closed_angles,
        closed_values,
        color=ACCENT_COLOR,
        alpha=0.18,
    )

    average_values = [
        50
        for _ in closed_angles
    ]

    axis.plot(
        closed_angles,
        average_values,
        color=TEXT_SECONDARY,
        linewidth=1,
        linestyle="--",
        alpha=0.7,
    )

    axis.set_title(
        "SCOUTING PROFILE",
        color=TEXT_PRIMARY,
        fontsize=13,
        fontweight="bold",
        pad=20,
    )

# SUMMARY METRICS
def draw_summary_metrics(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)
    add_panel(axis)
    add_section_title(axis, "Performance Summary")

    desired_metrics = [
        "pitch_count",
        "game_count",
        "strike_rate",
        "whiff_rate",
        "csw_rate",
        "chase_rate",
        "average_velocity",
        "hard_hit_rate",
        "expected_woba_allowed",
        "expected_slugging_allowed",
    ]

    summary_lookup = {
        card.get("key"): card
        for card in report.get(
            "summary_cards",
            [],
        )
    }

    metrics = [
        summary_lookup[key]
        for key in desired_metrics
        if key in summary_lookup
    ]

    if not metrics:
        axis.text(
            0.5,
            0.5,
            "No summary metrics available",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            ha="center",
            va="center",
        )
        return

    columns = 5
    rows = 2
    cell_width = 0.18
    cell_height = 0.31
    x_gap = 0.012
    y_positions = [
        0.49,
        0.12,
    ]

    for index, metric in enumerate(
        metrics[: columns * rows]
    ):
        row = index // columns
        column = index % columns

        x_position = (
            0.035
            + column
            * (
                cell_width
                + x_gap
            )
        )

        y_position = y_positions[row]

        metric_box = FancyBboxPatch(
            (
                x_position,
                y_position,
            ),
            cell_width,
            cell_height,
            transform=axis.transAxes,
            boxstyle=(
                "round,pad=0.01,"
                "rounding_size=0.02"
            ),
            linewidth=0,
            facecolor=PANEL_SECONDARY,
        )

        axis.add_patch(metric_box)

        axis.text(
            x_position + cell_width / 2,
            y_position + 0.19,
            metric.get(
                "display_value",
                "N/A",
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=12,
            fontweight="bold",
            ha="center",
            va="center",
        )

        axis.text(
            x_position + cell_width / 2,
            y_position + 0.07,
            metric.get(
                "name",
                "",
            ),
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            fontsize=7,
            ha="center",
            va="center",
        )

# PITCH HIGHLIGHTS
def draw_highlights(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)
    add_panel(axis)
    add_section_title(axis, "Pitch Highlights")

    highlights = report.get(
        "highlights",
        [],
    )

    if not highlights:
        axis.text(
            0.5,
            0.5,
            "No highlight data available",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            ha="center",
            va="center",
        )
        return

    card_height = 0.17
    start_y = 0.68
    vertical_gap = 0.035

    for index, highlight in enumerate(
        highlights[:4]
    ):
        y_position = (
            start_y
            - index
            * (
                card_height
                + vertical_gap
            )
        )

        pitch_color = get_pitch_color(
            highlight.get("pitch_type")
        )

        card = FancyBboxPatch(
            (
                0.05,
                y_position,
            ),
            0.90,
            card_height,
            transform=axis.transAxes,
            boxstyle=(
                "round,pad=0.012,"
                "rounding_size=0.02"
            ),
            linewidth=1.2,
            edgecolor=pitch_color,
            facecolor=PANEL_SECONDARY,
        )

        axis.add_patch(card)

        axis.text(
            0.08,
            y_position + 0.11,
            highlight.get(
                "title",
                "",
            ),
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            fontsize=7,
            fontweight="bold",
            ha="left",
            va="center",
        )

        axis.text(
            0.08,
            y_position + 0.045,
            highlight.get(
                "pitch_name",
                "",
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=9,
            fontweight="bold",
            ha="left",
            va="center",
        )

        axis.text(
            0.91,
            y_position + 0.085,
            highlight.get(
                "display_value",
                "",
            ),
            transform=axis.transAxes,
            color=pitch_color,
            fontsize=14,
            fontweight="bold",
            ha="right",
            va="center",
        )

# ARSENAL TABLE
def draw_arsenal_table(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)
    add_panel(axis)
    add_section_title(axis, "Pitch Arsenal")

    arsenal = report.get(
        "arsenal_table",
        [],
    )

    if not arsenal:
        axis.text(
            0.5,
            0.5,
            "No arsenal data available",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            ha="center",
            va="center",
        )
        return

    columns = [
        ("Pitch", 0.04, "left"),
        ("Use", 0.34, "center"),
        ("Velo", 0.45, "center"),
        ("Spin", 0.56, "center"),
        ("Whiff", 0.67, "center"),
        ("Chase", 0.78, "center"),
        ("Grade", 0.91, "center"),
    ]

    header_y = 0.81

    for label, x_position, alignment in columns:
        axis.text(
            x_position,
            header_y,
            label,
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            fontsize=8,
            fontweight="bold",
            ha=alignment,
            va="center",
        )

    maximum_rows = min(
        len(arsenal),
        7,
    )

    row_height = 0.095
    first_row_y = 0.71

    for index, pitch in enumerate(
        arsenal[:maximum_rows]
    ):
        y_position = (
            first_row_y
            - index * row_height
        )

        if index % 2 == 0:
            background = FancyBboxPatch(
                (
                    0.025,
                    y_position - 0.037,
                ),
                0.95,
                0.075,
                transform=axis.transAxes,
                boxstyle=(
                    "round,pad=0.003,"
                    "rounding_size=0.01"
                ),
                linewidth=0,
                facecolor=PANEL_SECONDARY,
                alpha=0.65,
            )

            axis.add_patch(background)

        pitch_type = pitch.get(
            "pitch_type",
            "",
        )

        pitch_color = get_pitch_color(
            pitch_type
        )

        axis.text(
            0.04,
            y_position,
            pitch_type,
            transform=axis.transAxes,
            color=pitch_color,
            fontsize=10,
            fontweight="bold",
            ha="left",
            va="center",
        )

        axis.text(
            0.10,
            y_position,
            shorten_text(
                pitch.get(
                    "pitch_name",
                    "",
                ),
                20,
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            ha="left",
            va="center",
        )

        axis.text(
            0.34,
            y_position,
            (
                f"{safe_float(pitch.get('usage_percent')):.1f}%"
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            ha="center",
            va="center",
        )

        axis.text(
            0.45,
            y_position,
            (
                f"{safe_float(pitch.get('average_velocity')):.1f}"
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            ha="center",
            va="center",
        )

        axis.text(
            0.56,
            y_position,
            (
                f"{safe_float(pitch.get('average_spin_rate')):.0f}"
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            ha="center",
            va="center",
        )

        axis.text(
            0.67,
            y_position,
            (
                f"{safe_float(pitch.get('whiff_rate')):.1f}%"
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            ha="center",
            va="center",
        )

        axis.text(
            0.78,
            y_position,
            (
                f"{safe_float(pitch.get('chase_rate')):.1f}%"
            ),
            transform=axis.transAxes,
            color=TEXT_PRIMARY,
            fontsize=8,
            ha="center",
            va="center",
        )

        overall_grade = pitch.get(
            "overall_pitch_grade"
        )

        if overall_grade is None:
            grade_text = "N/A"
            grade_color = TEXT_SECONDARY

        else:
            grade_value = safe_int(
                overall_grade,
                default=50,
            )

            grade_text = str(grade_value)

            grade_color = get_grade_color(
                pitch.get("color_group")
            )

        axis.text(
            0.91,
            y_position,
            grade_text,
            transform=axis.transAxes,
            color=grade_color,
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
        )

# STRENGTHS AND CONCERNS
def draw_strengths_and_concerns(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)
    add_panel(axis)

    strengths = report.get(
        "strengths",
        [],
    )

    concerns = report.get(
        "concerns",
        [],
    )

    axis.text(
        0.04,
        0.91,
        "STRENGTHS",
        transform=axis.transAxes,
        color="#4ADE80",
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="top",
    )

    y_position = 0.79

    if strengths:
        for strength in strengths[:4]:
            wrapped = wrap_text(
                strength,
                line_length=47,
            )

            axis.text(
                0.05,
                y_position,
                f"• {wrapped}",
                transform=axis.transAxes,
                color=TEXT_PRIMARY,
                fontsize=8,
                ha="left",
                va="top",
                linespacing=1.4,
            )

            line_count = max(
                1,
                wrapped.count("\n") + 1,
            )

            y_position -= (
                0.10
                + 0.05
                * (
                    line_count - 1
                )
            )

    else:
        axis.text(
            0.05,
            y_position,
            "No major strengths identified.",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            fontsize=8,
            ha="left",
            va="top",
        )

    axis.text(
        0.53,
        0.91,
        "CONCERNS",
        transform=axis.transAxes,
        color="#FB923C",
        fontsize=12,
        fontweight="bold",
        ha="left",
        va="top",
    )

    y_position = 0.79

    if concerns:
        for concern in concerns[:4]:
            wrapped = wrap_text(
                concern,
                line_length=43,
            )

            axis.text(
                0.54,
                y_position,
                f"• {wrapped}",
                transform=axis.transAxes,
                color=TEXT_PRIMARY,
                fontsize=8,
                ha="left",
                va="top",
                linespacing=1.4,
            )

            line_count = max(
                1,
                wrapped.count("\n") + 1,
            )

            y_position -= (
                0.10
                + 0.05
                * (
                    line_count - 1
                )
            )

    else:
        axis.text(
            0.54,
            y_position,
            "No major concerns identified.",
            transform=axis.transAxes,
            color=TEXT_SECONDARY,
            fontsize=8,
            ha="left",
            va="top",
        )

# SCOUTING SUMMARY
def draw_scouting_summary(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    remove_axis_decoration(axis)
    add_panel(
        axis,
        background=PANEL_SECONDARY,
    )

    add_section_title(
        axis,
        "Scouting Summary",
    )

    summary = report.get(
        "scouting_summary",
        "",
    )

    wrapped_summary = wrap_text(
        summary,
        line_length=140,
    )

    axis.text(
        0.04,
        0.68,
        wrapped_summary,
        transform=axis.transAxes,
        color=TEXT_PRIMARY,
        fontsize=9,
        ha="left",
        va="top",
        linespacing=1.5,
    )

# COMPLETE REPORT
def create_pitcher_report_card(
    report: dict[str, Any],
    output_path: str | Path,
    dpi: int = 200,
    show: bool = False,
) -> Path:
    """
    Generate a complete pitcher scouting report PNG.

    Parameters
    ----------
    report:
        Website-ready report returned by
        build_pitcher_report().

    output_path:
        File path for the generated PNG.

    dpi:
        Image resolution.

    show:
        Display the report after saving.

    Returns
    -------
    Path
        Final output path.
    """
    output = Path(output_path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure = plt.figure(
        figsize=(16, 19),
        facecolor=PAGE_BACKGROUND,
    )

    grid = figure.add_gridspec(
        nrows=24,
        ncols=12,
        left=0.035,
        right=0.965,
        top=0.975,
        bottom=0.025,
        hspace=0.9,
        wspace=0.8,
    )

    header_axis = figure.add_subplot(
        grid[0:2, 0:12]
    )

    grade_axis = figure.add_subplot(
        grid[2:5, 0:12]
    )

    radar_axis = figure.add_subplot(
        grid[5:12, 0:5],
        projection="polar",
    )

    summary_axis = figure.add_subplot(
        grid[5:10, 5:12]
    )

    highlights_axis = figure.add_subplot(
        grid[10:15, 5:12]
    )

    arsenal_axis = figure.add_subplot(
        grid[12:19, 0:7]
    )

    strengths_axis = figure.add_subplot(
        grid[15:19, 7:12]
    )

    scouting_axis = figure.add_subplot(
        grid[19:23, 0:12]
    )

    draw_header(
        header_axis,
        report,
    )

    draw_grade_cards(
        grade_axis,
        report,
    )

    draw_radar_chart(
        radar_axis,
        report,
    )

    draw_summary_metrics(
        summary_axis,
        report,
    )

    draw_highlights(
        highlights_axis,
        report,
    )

    draw_arsenal_table(
        arsenal_axis,
        report,
    )

    draw_strengths_and_concerns(
        strengths_axis,
        report,
    )

    draw_scouting_summary(
        scouting_axis,
        report,
    )

    figure.text(
        0.5,
        0.012,
        (
            "Generated from pitch-level Statcast data  •  "
            "20–80 grades are model estimates"
        ),
        color=TEXT_SECONDARY,
        fontsize=7,
        ha="center",
        va="bottom",
    )

    figure.savefig(
        output,
        dpi=dpi,
        facecolor=figure.get_facecolor(),
        bbox_inches="tight",
    )

    if show:
        plt.show()

    plt.close(figure)

    return output
