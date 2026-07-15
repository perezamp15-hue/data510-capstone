from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Any, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from visualizations.pitch_location_movement import (
    draw_pitch_location_heatmap,
)


# =============================================================================
# REPORT CONFIGURATION
# =============================================================================

REPORT_WIDTH = 17
REPORT_HEIGHT = 11

BACKGROUND_COLOR = "#FFFFFF"
PANEL_COLOR = "#FAFAFA"
PANEL_BORDER_COLOR = "#D5D5D5"
HEADER_COLOR = "#121820"
PRIMARY_TEXT_COLOR = "#1F2933"
SECONDARY_TEXT_COLOR = "#5A6470"
GRID_COLOR = "#D1D5DB"

PITCH_NAMES = {
    "FF": "4-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Forkball",
    "KN": "Knuckleball",
    "EP": "Eephus",
}

PITCH_COLORS = {
    "FF": "#D62728",
    "SI": "#FF7F0E",
    "FC": "#8C564B",
    "SL": "#1F77B4",
    "ST": "#9467BD",
    "CU": "#E377C2",
    "KC": "#BCBD22",
    "CH": "#2CA02C",
    "FS": "#17BECF",
    "FO": "#7F7F7F",
    "KN": "#AEC7E8",
    "EP": "#C5B0D5",
}

GRADE_ORDER = [
    ("stuff", "Stuff"),
    ("command", "Command"),
    ("bat_missing", "Bat Missing"),
    ("contact_management", "Contact Mgmt."),
    ("arsenal", "Arsenal"),
    ("overall", "Overall"),
]

SUMMARY_METRICS = [
    ("strike_rate", "Strike Rate", "%"),
    ("swing_rate", "Swing Rate", "%"),
    ("whiff_rate", "Whiff Rate", "%"),
    ("csw_rate", "CSW Rate", "%"),
    ("zone_rate", "Zone Rate", "%"),
    ("chase_rate", "Chase Rate", "%"),
    ("contact_rate", "Contact Rate", "%"),
    ("hard_hit_rate", "Hard-Hit Rate", "%"),
    ("xwoba", "xwOBA", ""),
]


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        number = float(value)

        if math.isfinite(number):
            return number

    except (TypeError, ValueError):
        pass

    return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    number = safe_float(value)

    if number is None:
        return default

    return int(round(number))


def first_available(
    mapping: dict[str, Any],
    keys: list[str],
    default: Any = None,
) -> Any:
    for key in keys:
        value = mapping.get(key)

        if value is not None:
            return value

    return default


def format_percentage(
    value: Any,
    decimals: int = 1,
) -> str:
    number = safe_float(value)

    if number is None:
        return "—"

    return f"{number:.{decimals}f}%"


def format_decimal(
    value: Any,
    decimals: int = 3,
) -> str:
    number = safe_float(value)

    if number is None:
        return "—"

    formatted = f"{number:.{decimals}f}"

    if abs(number) < 1:
        return formatted.lstrip("0")

    return formatted


def format_number(
    value: Any,
    decimals: int = 1,
) -> str:
    number = safe_float(value)

    if number is None:
        return "—"

    return f"{number:.{decimals}f}"


def format_integer(
    value: Any,
) -> str:
    number = safe_float(value)

    if number is None:
        return "—"

    return f"{int(round(number)):,}"


def hide_axis(axis: Axes) -> None:
    axis.set_xticks([])
    axis.set_yticks([])

    for spine in axis.spines.values():
        spine.set_visible(False)


def add_panel_background(
    axis: Axes,
    title: Optional[str] = None,
) -> None:
    """
    Apply a consistent panel background.

    Panel titles are deliberately placed above the plotting area with
    Axes.set_title(). This prevents titles from covering bars, points,
    tables, or heatmaps.
    """
    axis.set_facecolor(PANEL_COLOR)

    for spine in axis.spines.values():
        spine.set_visible(True)
        spine.set_color(PANEL_BORDER_COLOR)
        spine.set_linewidth(0.8)

    if title:
        axis.set_title(
            title.upper(),
            loc="left",
            fontsize=11,
            fontweight="bold",
            color="#333333",
            pad=12,
        )


def normalize_report(
    report: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(report)

    normalized.setdefault("pitcher_name", "Unknown Pitcher")
    normalized.setdefault("season", "")
    normalized.setdefault("team_name", "")
    normalized.setdefault("throws", "")
    normalized.setdefault("grades", {})
    normalized.setdefault("summary", {})
    normalized.setdefault("arsenal_table", [])
    normalized.setdefault("movement_chart", [])
    normalized.setdefault("pitch_locations", [])
    normalized.setdefault("strengths", [])
    normalized.setdefault("concerns", [])
    normalized.setdefault("scouting_summary", "")
    normalized.setdefault("splits", {})

    return normalized


def add_page_title(
    figure: Figure,
    title: str,
    subtitle: str = "",
) -> None:
    figure.text(
        0.045,
        0.972,
        title,
        fontsize=17,
        fontweight="bold",
        ha="left",
        va="top",
        color=PRIMARY_TEXT_COLOR,
    )

    if subtitle:
        figure.text(
            0.045,
            0.944,
            subtitle,
            fontsize=8.5,
            ha="left",
            va="top",
            color=SECONDARY_TEXT_COLOR,
        )


# =============================================================================
# HEADER
# =============================================================================

def draw_header(
    axis: Axes,
    report: dict[str, Any],
) -> None:
    hide_axis(axis)

    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.set_facecolor(HEADER_COLOR)

    pitcher_name = report.get(
        "pitcher_name",
        "Unknown Pitcher",
    )

    season = report.get("season", "")
    team_name = report.get("team_name", "")
    throws = report.get("throws", "")

    subtitle_parts = [
        str(value)
        for value in [team_name, throws, season]
        if value not in (None, "")
    ]

    subtitle = "  |  ".join(subtitle_parts)

    axis.text(
        0.025,
        0.68,
        pitcher_name,
        fontsize=24,
        fontweight="bold",
        color="white",
        ha="left",
        va="center",
    )

    axis.text(
        0.027,
        0.28,
        subtitle,
        fontsize=11,
        color="#D6DCE4",
        ha="left",
        va="center",
    )

    summary = report.get("summary", {})

    workload_items = [
        (
            "GAMES",
            first_available(
                summary,
                ["game_count", "games"],
                0,
            ),
        ),
        (
            "PITCHES",
            first_available(
                summary,
                ["pitch_count", "pitches"],
                0,
            ),
        ),
        (
            "PA",
            first_available(
                summary,
                ["plate_appearances", "pa"],
                0,
            ),
        ),
        (
            "BATTERS",
            first_available(
                summary,
                ["batter_count", "batters_faced"],
                0,
            ),
        ),
    ]

    starting_x = 0.63
    item_width = 0.087

    for index, (label, value) in enumerate(workload_items):
        x_position = starting_x + index * item_width

        axis.text(
            x_position,
            0.68,
            format_integer(value),
            fontsize=15,
            fontweight="bold",
            color="white",
            ha="center",
            va="center",
        )

        axis.text(
            x_position,
            0.30,
            label,
            fontsize=7.5,
            color="#C0C6CE",
            ha="center",
            va="center",
        )


# =============================================================================
# SCOUTING GRADES
# =============================================================================

def draw_grades(
    axis: Axes,
    grades: dict[str, Any],
) -> None:
    add_panel_background(
        axis,
        "Scouting Grades",
    )

    axis.set_xlim(20, 80)
    axis.set_ylim(
        -0.35,
        len(GRADE_ORDER) - 0.1,
    )
    axis.invert_yaxis()

    labels: list[str] = []
    values: list[float] = []

    for key, label in GRADE_ORDER:
        labels.append(label)

        value = safe_float(
            grades.get(key),
            50.0,
        )

        values.append(
            min(
                max(value or 50.0, 20.0),
                80.0,
            )
        )

    y_positions = np.arange(len(labels))

    axis.barh(
        y_positions,
        [60] * len(labels),
        left=20,
        height=0.48,
        color="#E8E8E8",
        edgecolor="none",
    )

    bar_colors = [
        "#B22222" if label == "Overall" else "#434E5B"
        for label in labels
    ]

    axis.barh(
        y_positions,
        np.array(values) - 20,
        left=20,
        height=0.48,
        color=bar_colors,
        edgecolor="none",
    )

    for y_position, value in zip(
        y_positions,
        values,
    ):
        axis.text(
            value + 1.2,
            y_position,
            f"{value:.0f}",
            ha="left",
            va="center",
            fontsize=8.5,
            fontweight="bold",
        )

    axis.set_yticks(y_positions)
    axis.set_yticklabels(
        labels,
        fontsize=8,
    )

    axis.set_xticks(
        [20, 30, 40, 50, 60, 70, 80]
    )

    axis.tick_params(
        axis="x",
        labelsize=7,
        length=0,
    )

    axis.grid(
        axis="x",
        alpha=0.15,
        linewidth=0.6,
    )

    axis.set_axisbelow(True)


# =============================================================================
# PERFORMANCE SUMMARY
# =============================================================================

def draw_performance_summary(
    axis: Axes,
    summary: dict[str, Any],
) -> None:
    add_panel_background(
        axis,
        "Performance Summary",
    )

    hide_axis(axis)

    metric_rows = [
        SUMMARY_METRICS[:3],
        SUMMARY_METRICS[3:6],
        SUMMARY_METRICS[6:],
    ]

    y_positions = [
        0.72,
        0.43,
        0.14,
    ]

    for row_index, row in enumerate(metric_rows):
        item_width = 1.0 / len(row)

        for item_index, (
            key,
            label,
            suffix,
        ) in enumerate(row):
            x_position = (
                item_index * item_width
                + item_width / 2
            )

            value = summary.get(key)

            if key == "xwoba":
                displayed_value = format_decimal(
                    value,
                    decimals=3,
                )

            elif suffix == "%":
                displayed_value = format_percentage(
                    value,
                    decimals=1,
                )

            else:
                displayed_value = format_number(
                    value,
                    decimals=1,
                )

            axis.text(
                x_position,
                y_positions[row_index] + 0.075,
                displayed_value,
                transform=axis.transAxes,
                ha="center",
                va="center",
                fontsize=12,
                fontweight="bold",
                color=PRIMARY_TEXT_COLOR,
            )

            axis.text(
                x_position,
                y_positions[row_index] - 0.035,
                label,
                transform=axis.transAxes,
                ha="center",
                va="center",
                fontsize=7.5,
                color=SECONDARY_TEXT_COLOR,
            )


# =============================================================================
# ARSENAL TABLE
# =============================================================================

def prepare_arsenal_dataframe(
    arsenal_table: list[dict[str, Any]],
) -> pd.DataFrame:
    dataframe = pd.DataFrame(arsenal_table)

    if dataframe.empty:
        return dataframe

    pitch_column = None

    for candidate in [
        "pitch_type",
        "pitch",
        "code",
    ]:
        if candidate in dataframe.columns:
            pitch_column = candidate
            break

    if pitch_column is None:
        dataframe["pitch_type"] = "UNK"

    elif pitch_column != "pitch_type":
        dataframe["pitch_type"] = (
            dataframe[pitch_column]
        )

    rename_candidates = {
        "usage": "usage_percentage",
        "usage_rate": "usage_percentage",
        "avg_velocity": "average_velocity",
        "velocity": "average_velocity",
        "avg_spin": "average_spin_rate",
        "spin_rate": "average_spin_rate",
        "average_release_spin_rate": (
            "average_spin_rate"
        ),
        "horizontal_break": (
            "average_horizontal_break"
        ),
        "vertical_break": (
            "average_vertical_break"
        ),
        "strike_rate": "strike_percentage",
        "whiff_rate": "whiff_percentage",
        "chase_rate": "chase_percentage",
    }

    for source, target in (
        rename_candidates.items()
    ):
        if (
            source in dataframe.columns
            and target not in dataframe.columns
        ):
            dataframe[target] = (
                dataframe[source]
            )

    numeric_columns = [
        "pitch_count",
        "usage_percentage",
        "average_velocity",
        "average_spin_rate",
        "average_horizontal_break",
        "average_vertical_break",
        "strike_percentage",
        "whiff_percentage",
        "chase_percentage",
    ]

    for column in numeric_columns:
        if column not in dataframe.columns:
            dataframe[column] = np.nan

        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe["pitch_name"] = (
        dataframe["pitch_type"]
        .map(PITCH_NAMES)
        .fillna(dataframe["pitch_type"])
    )

    dataframe = dataframe.sort_values(
        by="usage_percentage",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    return dataframe


def draw_arsenal_table(
    axis: Axes,
    arsenal_table: list[dict[str, Any]],
) -> None:
    add_panel_background(
        axis,
        "Pitch Arsenal",
    )

    hide_axis(axis)

    dataframe = prepare_arsenal_dataframe(
        arsenal_table
    )

    if dataframe.empty:
        axis.text(
            0.5,
            0.48,
            "Arsenal data is unavailable",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            color="#777777",
        )
        return

    columns = [
        ("pitch_name", "PITCH"),
        ("pitch_count", "COUNT"),
        ("usage_percentage", "USAGE"),
        ("average_velocity", "VELO"),
        ("average_spin_rate", "SPIN"),
        ("average_horizontal_break", "HB"),
        ("average_vertical_break", "IVB"),
        ("strike_percentage", "STRIKE"),
        ("whiff_percentage", "WHIFF"),
        ("chase_percentage", "CHASE"),
    ]

    column_widths = [
        0.16,
        0.08,
        0.09,
        0.08,
        0.09,
        0.08,
        0.08,
        0.10,
        0.10,
        0.10,
    ]

    starting_x = 0.02
    header_y = 0.84
    row_start_y = 0.69
    row_spacing = 0.105

    x_positions: list[float] = []
    cumulative = starting_x

    for width in column_widths:
        x_positions.append(cumulative)
        cumulative += width

    for x_position, (
        _,
        label,
    ), width in zip(
        x_positions,
        columns,
        column_widths,
    ):
        alignment = (
            "left"
            if label == "PITCH"
            else "center"
        )

        text_x = (
            x_position
            if alignment == "left"
            else x_position + width / 2
        )

        axis.text(
            text_x,
            header_y,
            label,
            transform=axis.transAxes,
            ha=alignment,
            va="center",
            fontsize=7.5,
            fontweight="bold",
            color="#4A5561",
        )

    max_rows = min(
        len(dataframe),
        7,
    )

    for row_index in range(max_rows):
        row = dataframe.iloc[row_index]
        y_position = (
            row_start_y
            - row_index * row_spacing
        )

        if row_index % 2 == 0:
            axis.add_patch(
                Rectangle(
                    (
                        0.012,
                        y_position - 0.058,
                    ),
                    0.976,
                    0.115,
                    transform=axis.transAxes,
                    facecolor="#F1F3F5",
                    edgecolor="none",
                    zorder=0,
                )
            )

        pitch_type = str(
            row.get(
                "pitch_type",
                "UNK",
            )
        )

        formatted_values = {
            "pitch_name": row.get(
                "pitch_name",
                pitch_type,
            ),
            "pitch_count": format_integer(
                row.get("pitch_count")
            ),
            "usage_percentage": (
                format_percentage(
                    row.get("usage_percentage")
                )
            ),
            "average_velocity": format_number(
                row.get("average_velocity")
            ),
            "average_spin_rate": format_integer(
                row.get("average_spin_rate")
            ),
            "average_horizontal_break": (
                format_number(
                    row.get(
                        "average_horizontal_break"
                    )
                )
            ),
            "average_vertical_break": (
                format_number(
                    row.get(
                        "average_vertical_break"
                    )
                )
            ),
            "strike_percentage": (
                format_percentage(
                    row.get("strike_percentage")
                )
            ),
            "whiff_percentage": (
                format_percentage(
                    row.get("whiff_percentage")
                )
            ),
            "chase_percentage": (
                format_percentage(
                    row.get("chase_percentage")
                )
            ),
        }

        for x_position, (
            key,
            _,
        ), width in zip(
            x_positions,
            columns,
            column_widths,
        ):
            alignment = (
                "left"
                if key == "pitch_name"
                else "center"
            )

            text_x = (
                x_position
                if alignment == "left"
                else x_position + width / 2
            )

            axis.text(
                text_x,
                y_position,
                formatted_values[key],
                transform=axis.transAxes,
                ha=alignment,
                va="center",
                fontsize=7.8,
                fontweight=(
                    "bold"
                    if key == "pitch_name"
                    else "normal"
                ),
                color=(
                    PITCH_COLORS.get(
                        pitch_type,
                        "#333333",
                    )
                    if key == "pitch_name"
                    else "#26313B"
                ),
            )


# =============================================================================
# MOVEMENT PROFILE
# =============================================================================

def draw_final_movement_profile(
    axis: Axes,
    movement_data: list[dict[str, Any]],
    title: Optional[str] = None,
) -> None:
    movement_frame = pd.DataFrame(
        movement_data
    )

    add_panel_background(
        axis,
        title,
    )

    if movement_frame.empty:
        axis.text(
            0.5,
            0.5,
            "Movement data is unavailable",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=10,
        )
        return

    rename_mapping = {
        "average_horizontal_break": (
            "horizontal_break"
        ),
        "average_vertical_break": (
            "vertical_break"
        ),
    }

    for source, target in (
        rename_mapping.items()
    ):
        if (
            source in movement_frame.columns
            and target not in movement_frame.columns
        ):
            movement_frame[target] = (
                movement_frame[source]
            )

    required_columns = [
        "pitch_type",
        "horizontal_break",
        "vertical_break",
    ]

    missing = [
        column
        for column in required_columns
        if column not in movement_frame.columns
    ]

    if missing:
        axis.text(
            0.5,
            0.5,
            "Movement data is incomplete",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
        return

    for column in [
        "horizontal_break",
        "vertical_break",
        "usage_percentage",
    ]:
        if column not in movement_frame.columns:
            movement_frame[column] = np.nan

        movement_frame[column] = pd.to_numeric(
            movement_frame[column],
            errors="coerce",
        )

    movement_frame = movement_frame.dropna(
        subset=[
            "horizontal_break",
            "vertical_break",
        ]
    )

    if movement_frame.empty:
        axis.text(
            0.5,
            0.5,
            "Movement data is unavailable",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
        return

    axis.axhline(
        0,
        linewidth=0.7,
        color="#777777",
        alpha=0.65,
    )

    axis.axvline(
        0,
        linewidth=0.7,
        color="#777777",
        alpha=0.65,
    )

    for row in movement_frame.itertuples(
        index=False
    ):
        pitch_type = str(
            row.pitch_type
        )

        usage = safe_float(
            getattr(
                row,
                "usage_percentage",
                0,
            ),
            0,
        ) or 0

        marker_size = (
            80
            + usage * 9
        )

        axis.scatter(
            row.horizontal_break,
            row.vertical_break,
            s=marker_size,
            color=PITCH_COLORS.get(
                pitch_type,
                "#64748B",
            ),
            edgecolors="#222222",
            linewidths=0.8,
            alpha=0.88,
            zorder=3,
        )

        axis.annotate(
            pitch_type,
            (
                row.horizontal_break,
                row.vertical_break,
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            fontweight="bold",
            color="#111111",
        )

    horizontal_values = (
        movement_frame["horizontal_break"]
    )

    vertical_values = (
        movement_frame["vertical_break"]
    )

    axis.set_xlim(
        min(
            -5,
            horizontal_values.min() - 3,
        ),
        max(
            5,
            horizontal_values.max() + 3,
        ),
    )

    axis.set_ylim(
        min(
            -5,
            vertical_values.min() - 3,
        ),
        max(
            5,
            vertical_values.max() + 3,
        ),
    )

    axis.set_xlabel(
        "Horizontal movement (inches)",
        fontsize=8,
    )

    axis.set_ylabel(
        "Induced vertical break (inches)",
        fontsize=8,
    )

    axis.tick_params(
        labelsize=7.5,
    )

    axis.grid(
        alpha=0.15,
        linewidth=0.5,
    )

    axis.text(
        0.985,
        0.025,
        "Bubble size = usage",
        transform=axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="#666666",
        bbox={
            "facecolor": PANEL_COLOR,
            "edgecolor": "none",
            "alpha": 0.80,
            "pad": 1.5,
        },
    )

    axis.text(
        0.015,
        0.025,
        "Arm-side movement",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=7,
        color=SECONDARY_TEXT_COLOR,
        bbox={
            "facecolor": PANEL_COLOR,
            "edgecolor": "none",
            "alpha": 0.80,
            "pad": 1.5,
        },
    )

    axis.text(
        0.50,
        0.965,
        "More vertical carry",
        transform=axis.transAxes,
        ha="center",
        va="top",
        fontsize=7,
        color=SECONDARY_TEXT_COLOR,
        bbox={
            "facecolor": PANEL_COLOR,
            "edgecolor": "none",
            "alpha": 0.80,
            "pad": 1.5,
        },
    )


# =============================================================================
# PITCH USAGE
# =============================================================================

def draw_pitch_usage(
    axis: Axes,
    arsenal_table: list[dict[str, Any]],
    title: Optional[str] = None,
) -> None:
    add_panel_background(
        axis,
        title,
    )

    dataframe = prepare_arsenal_dataframe(
        arsenal_table
    )

    if dataframe.empty:
        hide_axis(axis)

        axis.text(
            0.5,
            0.5,
            "Usage data is unavailable",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="#777777",
        )
        return

    dataframe["usage_percentage"] = (
        pd.to_numeric(
            dataframe["usage_percentage"],
            errors="coerce",
        )
    )

    if (
        dataframe[
            "usage_percentage"
        ].notna().sum()
        == 0
    ):
        dataframe["pitch_count"] = (
            pd.to_numeric(
                dataframe["pitch_count"],
                errors="coerce",
            )
        )

        total_pitch_count = (
            dataframe["pitch_count"].sum(
                skipna=True
            )
        )

        if (
            pd.notna(total_pitch_count)
            and total_pitch_count > 0
        ):
            dataframe["usage_percentage"] = (
                dataframe["pitch_count"]
                / total_pitch_count
                * 100.0
            )

    dataframe = dataframe[
        dataframe["usage_percentage"].notna()
        & np.isfinite(
            dataframe["usage_percentage"]
        )
        & (
            dataframe["usage_percentage"]
            >= 0
        )
    ].copy()

    if dataframe.empty:
        hide_axis(axis)

        axis.text(
            0.5,
            0.5,
            "Usage data is unavailable",
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="#777777",
        )
        return

    dataframe = (
        dataframe
        .sort_values(
            by="usage_percentage",
            ascending=False,
        )
        .head(7)
        .sort_values(
            by="usage_percentage",
            ascending=True,
        )
    )

    colors = [
        PITCH_COLORS.get(
            str(pitch_type),
            "#64748B",
        )
        for pitch_type in (
            dataframe["pitch_type"]
        )
    ]

    y_positions = np.arange(
        len(dataframe)
    )

    axis.barh(
        y_positions,
        dataframe["usage_percentage"],
        color=colors,
        edgecolor="none",
        height=0.58,
    )

    axis.set_yticks(
        y_positions
    )

    axis.set_yticklabels(
        dataframe["pitch_type"],
        fontsize=8.5,
        fontweight="bold",
    )

    for y_position, usage in zip(
        y_positions,
        dataframe["usage_percentage"],
    ):
        axis.text(
            float(usage) + 0.5,
            y_position,
            f"{float(usage):.1f}%",
            ha="left",
            va="center",
            fontsize=8,
        )

    maximum_usage = (
        dataframe["usage_percentage"].max()
    )

    if (
        pd.isna(maximum_usage)
        or not np.isfinite(maximum_usage)
        or maximum_usage <= 0
    ):
        maximum_usage = 10.0

    axis.set_xlim(
        0,
        float(maximum_usage) * 1.25,
    )

    axis.set_xlabel(
        "Usage percentage",
        fontsize=8,
    )

    axis.tick_params(
        axis="x",
        labelsize=7.5,
    )

    axis.grid(
        axis="x",
        alpha=0.15,
        linewidth=0.5,
    )

    axis.set_axisbelow(True)


# =============================================================================
# PITCH LOCATION PANELS
# =============================================================================

def draw_location_panels(
    axes: list[Axes],
    pitch_locations: list[dict[str, Any]],
    top_n: int = 6,
) -> None:
    location_frame = pd.DataFrame(
        pitch_locations
    )

    if location_frame.empty:
        for axis in axes:
            add_panel_background(
                axis,
                None,
            )

            hide_axis(axis)

            axis.text(
                0.5,
                0.5,
                "Location data unavailable",
                transform=axis.transAxes,
                ha="center",
                va="center",
                fontsize=9,
            )

        return

    required_columns = [
        "pitch_type",
        "plate_crossing_x",
        "plate_crossing_z",
    ]

    if any(
        column not in location_frame.columns
        for column in required_columns
    ):
        for axis in axes:
            add_panel_background(
                axis,
                None,
            )

            hide_axis(axis)

            axis.text(
                0.5,
                0.5,
                "Location data incomplete",
                transform=axis.transAxes,
                ha="center",
                va="center",
            )

        return

    top_pitch_types = (
        location_frame["pitch_type"]
        .value_counts()
        .head(top_n)
        .index
        .tolist()
    )

    for axis_index, axis in enumerate(
        axes
    ):
        if axis_index >= len(
            top_pitch_types
        ):
            hide_axis(axis)
            continue

        pitch_type = (
            top_pitch_types[axis_index]
        )

        draw_pitch_location_heatmap(
            axis=axis,
            pitch_data=location_frame,
            pitch_type=pitch_type,
        )

        pitch_count = int(
            (
                location_frame["pitch_type"]
                == pitch_type
            ).sum()
        )

        pitch_name = PITCH_NAMES.get(
            str(pitch_type),
            str(pitch_type),
        )

        axis.set_title(
            (
                f"{pitch_name}\n"
                f"{pitch_count:,} pitches"
            ),
            fontsize=9,
            fontweight="bold",
            pad=12,
            linespacing=1.15,
        )

        axis.set_xlabel(
            "Horizontal location",
            fontsize=7.5,
        )

        axis.set_ylabel(
            "Height",
            fontsize=7.5,
        )

        axis.tick_params(
            labelsize=7,
        )


# =============================================================================
# HANDEDNESS SPLITS
# =============================================================================

def draw_splits(
    axis: Axes,
    splits: dict[str, Any],
) -> None:
    add_panel_background(
        axis,
        "Handedness Splits",
    )

    hide_axis(axis)

    left_split = first_available(
        splits,
        [
            "vs_lhb",
            "left",
            "L",
        ],
        {},
    ) or {}

    right_split = first_available(
        splits,
        [
            "vs_rhb",
            "right",
            "R",
        ],
        {},
    ) or {}

    if (
        not left_split
        and not right_split
    ):
        axis.text(
            0.5,
            0.48,
            (
                "Handedness splits "
                "not yet available"
            ),
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=9,
            color="#777777",
        )
        return

    metrics = [
        (
            "plate_appearances",
            "PA",
            format_integer,
        ),
        (
            "whiff_rate",
            "Whiff",
            format_percentage,
        ),
        (
            "strikeout_rate",
            "K Rate",
            format_percentage,
        ),
        (
            "walk_rate",
            "BB Rate",
            format_percentage,
        ),
        (
            "xwoba",
            "xwOBA",
            format_decimal,
        ),
        (
            "hard_hit_rate",
            "Hard Hit",
            format_percentage,
        ),
    ]

    axis.text(
        0.50,
        0.79,
        "VS LHB",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
    )

    axis.text(
        0.82,
        0.79,
        "VS RHB",
        transform=axis.transAxes,
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
    )

    starting_y = 0.65
    spacing = 0.105

    for index, (
        key,
        label,
        formatter,
    ) in enumerate(metrics):
        y_position = (
            starting_y
            - index * spacing
        )

        axis.text(
            0.08,
            y_position,
            label,
            transform=axis.transAxes,
            ha="left",
            va="center",
            fontsize=7.8,
            color="#4B5563",
        )

        axis.text(
            0.50,
            y_position,
            formatter(
                left_split.get(key)
            ),
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=8.2,
            fontweight="bold",
        )

        axis.text(
            0.82,
            y_position,
            formatter(
                right_split.get(key)
            ),
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=8.2,
            fontweight="bold",
        )


# =============================================================================
# STRENGTHS, CONCERNS, AND SUMMARY
# =============================================================================

def draw_bullet_panel(
    axis: Axes,
    title: str,
    items: list[str],
) -> None:
    add_panel_background(
        axis,
        title,
    )

    hide_axis(axis)

    if not items:
        items = [
            "No automated findings available."
        ]

    y_position = 0.76

    for item in items[:4]:
        wrapped_lines = textwrap.wrap(
            str(item),
            width=48,
            break_long_words=False,
            break_on_hyphens=False,
        )

        axis.text(
            0.05,
            y_position,
            "•",
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=12,
            fontweight="bold",
        )

        axis.text(
            0.11,
            y_position,
            "\n".join(wrapped_lines),
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=8.2,
            linespacing=1.30,
            color="#303942",
        )

        y_position -= (
            0.17
            + max(
                0,
                len(wrapped_lines) - 1,
            )
            * 0.060
        )


def draw_scouting_summary(
    axis: Axes,
    summary_text: str,
) -> None:
    """Draw a readable scouting summary without clipping."""
    add_panel_background(
        axis,
        "Scouting Summary",
    )

    hide_axis(axis)

    wrapped_summary = textwrap.fill(
        str(summary_text or ""),
        width=95,
        break_long_words=False,
        break_on_hyphens=False,
    )

    axis.text(
        0.035,
        0.82,
        wrapped_summary,
        transform=axis.transAxes,
        fontsize=9.4,
        color="#303942",
        ha="left",
        va="top",
        linespacing=1.42,
        wrap=True,
        clip_on=True,
    )


# =============================================================================
# LANDSCAPE MULTI-PAGE REPORT LAYOUT
# =============================================================================

TOTAL_PDF_PAGES = 5


def add_report_footer(
    figure: Figure,
    report: dict[str, Any],
    page_number: int,
    total_pages: int = TOTAL_PDF_PAGES,
) -> None:
    """Add a consistent footer outside all chart panels."""
    pitcher_name = str(
        report.get(
            "pitcher_name",
            "Unknown Pitcher",
        )
    )
    season = str(
        report.get(
            "season",
            "",
        )
    )

    figure.add_artist(
        plt.Line2D(
            [0.045, 0.955],
            [0.042, 0.042],
            transform=figure.transFigure,
            color=PANEL_BORDER_COLOR,
            linewidth=0.8,
        )
    )

    figure.text(
        0.045,
        0.022,
        f"{pitcher_name} | {season}",
        ha="left",
        va="bottom",
        fontsize=7.5,
        color=SECONDARY_TEXT_COLOR,
    )

    figure.text(
        0.955,
        0.022,
        f"Page {page_number} of {total_pages}",
        ha="right",
        va="bottom",
        fontsize=7.5,
        color=SECONDARY_TEXT_COLOR,
    )


def add_section_header(
    figure: Figure,
    title: str,
    subtitle: str = "",
) -> None:
    """Create a full-width landscape page header."""
    header_axis = figure.add_axes(
        [0.0, 0.89, 1.0, 0.11]
    )

    hide_axis(header_axis)
    header_axis.set_facecolor(
        HEADER_COLOR
    )

    header_axis.text(
        0.045,
        0.62,
        title,
        ha="left",
        va="center",
        fontsize=22,
        fontweight="bold",
        color="white",
    )

    if subtitle:
        header_axis.text(
            0.046,
            0.24,
            subtitle,
            ha="left",
            va="center",
            fontsize=9.5,
            color="#D6DCE4",
        )


def draw_secondary_metrics(
    axis: Axes,
    summary: dict[str, Any],
) -> None:
    """Display additional physical and contact-quality metrics."""
    add_panel_background(
        axis,
        "Additional Metrics",
    )

    hide_axis(axis)

    metrics = [
        (
            "average_velocity",
            "Average Velocity",
            lambda value: (
                f"{format_number(value, 1)} mph"
                if safe_float(value) is not None
                else "—"
            ),
        ),
        (
            "average_spin_rate",
            "Average Spin",
            lambda value: (
                f"{format_integer(value)} rpm"
                if safe_float(value) is not None
                else "—"
            ),
        ),
        (
            "average_extension",
            "Extension",
            lambda value: (
                f"{format_number(value, 1)} ft"
                if safe_float(value) is not None
                else "—"
            ),
        ),
        (
            "average_exit_velocity",
            "Average Exit Velocity",
            lambda value: (
                f"{format_number(value, 1)} mph"
                if safe_float(value) is not None
                else "—"
            ),
        ),
        (
            "sweet_spot_rate",
            "Sweet-Spot Rate",
            lambda value: (
                format_percentage(
                    value,
                    1,
                )
            ),
        ),
        (
            "xslg",
            "xSLG",
            lambda value: (
                format_decimal(
                    value,
                    3,
                )
            ),
        ),
    ]

    row_y = [
        0.71,
        0.44,
        0.17,
    ]

    column_x = [
        0.25,
        0.75,
    ]

    for index, (
        key,
        label,
        formatter,
    ) in enumerate(metrics):
        row_index = index // 2
        column_index = index % 2

        axis.text(
            column_x[column_index],
            row_y[row_index] + 0.07,
            formatter(
                summary.get(key)
            ),
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=PRIMARY_TEXT_COLOR,
        )

        axis.text(
            column_x[column_index],
            row_y[row_index] - 0.04,
            label,
            transform=axis.transAxes,
            ha="center",
            va="center",
            fontsize=7.8,
            color=SECONDARY_TEXT_COLOR,
        )


def build_overview_page(
    report: dict[str, Any],
) -> Figure:
    """Page 1: landscape scouting overview."""
    figure = plt.figure(
        figsize=(
            REPORT_WIDTH,
            REPORT_HEIGHT,
        ),
        facecolor=BACKGROUND_COLOR,
    )

    grid = figure.add_gridspec(
        nrows=30,
        ncols=18,
        left=0.045,
        right=0.955,
        top=0.965,
        bottom=0.070,
        hspace=1.20,
        wspace=1.05,
    )

    header_axis = figure.add_subplot(
        grid[0:4, 0:18]
    )

    grades_axis = figure.add_subplot(
        grid[5:15, 0:7]
    )

    performance_axis = figure.add_subplot(
        grid[5:15, 7:18]
    )

    strengths_axis = figure.add_subplot(
        grid[16:25, 0:7]
    )

    concerns_axis = figure.add_subplot(
        grid[16:25, 7:14]
    )

    metrics_axis = figure.add_subplot(
        grid[16:25, 14:18]
    )

    draw_header(
        header_axis,
        report,
    )

    draw_grades(
        grades_axis,
        report.get(
            "grades",
            {},
        ),
    )

    draw_performance_summary(
        performance_axis,
        report.get(
            "summary",
            {},
        ),
    )

    draw_bullet_panel(
        strengths_axis,
        "Strengths",
        [
            str(item)
            for item in report.get(
                "strengths",
                [],
            )
        ],
    )

    draw_bullet_panel(
        concerns_axis,
        "Development Areas",
        [
            str(item)
            for item in report.get(
                "concerns",
                [],
            )
        ],
    )

    draw_secondary_metrics(
        metrics_axis,
        report.get(
            "summary",
            {},
        ),
    )

    add_report_footer(
        figure,
        report,
        1,
    )

    return figure


def build_arsenal_page(
    report: dict[str, Any],
) -> Figure:
    """Page 2: full arsenal table and usage distribution."""
    figure = plt.figure(
        figsize=(
            REPORT_WIDTH,
            REPORT_HEIGHT,
        ),
        facecolor=BACKGROUND_COLOR,
    )

    pitcher_name = report.get(
        "pitcher_name",
        "Unknown Pitcher",
    )
    season = report.get(
        "season",
        "",
    )

    add_section_header(
        figure,
        "Pitch Arsenal",
        (
            f"{pitcher_name} | {season} | "
            "Usage, velocity, movement, and pitch results"
        ),
    )

    grid = figure.add_gridspec(
        nrows=27,
        ncols=18,
        left=0.045,
        right=0.955,
        top=0.845,
        bottom=0.070,
        hspace=1.35,
        wspace=1.00,
    )

    arsenal_axis = figure.add_subplot(
        grid[0:18, 0:18]
    )

    usage_axis = figure.add_subplot(
        grid[20:27, 0:18]
    )

    draw_arsenal_table(
        arsenal_axis,
        report.get(
            "arsenal_table",
            [],
        ),
    )

    draw_pitch_usage(
        usage_axis,
        report.get(
            "arsenal_table",
            [],
        ),
        title="Usage Distribution",
    )

    add_report_footer(
        figure,
        report,
        2,
    )

    return figure


def build_characteristics_page(
    report: dict[str, Any],
) -> Figure:
    """Page 3: movement, splits, and scouting summary."""
    figure = plt.figure(
        figsize=(
            REPORT_WIDTH,
            REPORT_HEIGHT,
        ),
        facecolor=BACKGROUND_COLOR,
    )

    pitcher_name = report.get(
        "pitcher_name",
        "Unknown Pitcher",
    )
    season = report.get(
        "season",
        "",
    )

    add_section_header(
        figure,
        "Pitch Characteristics",
        (
            f"{pitcher_name} | {season} | "
            "Shape, separation, and matchup profile"
        ),
    )

    grid = figure.add_gridspec(
        nrows=28,
        ncols=18,
        left=0.045,
        right=0.955,
        top=0.845,
        bottom=0.070,
        hspace=1.45,
        wspace=1.20,
    )

    movement_axis = figure.add_subplot(
        grid[0:17, 0:12]
    )

    usage_axis = figure.add_subplot(
        grid[0:17, 12:18]
    )

    splits_axis = figure.add_subplot(
        grid[19:28, 0:7]
    )

    summary_axis = figure.add_subplot(
        grid[19:28, 7:18]
    )

    draw_final_movement_profile(
        movement_axis,
        report.get(
            "movement_chart",
            [],
        ),
        title="Movement Profile",
    )

    draw_pitch_usage(
        usage_axis,
        report.get(
            "arsenal_table",
            [],
        ),
        title="Pitch Usage",
    )

    draw_splits(
        splits_axis,
        report.get(
            "splits",
            {},
        ),
    )

    draw_scouting_summary(
        summary_axis,
        report.get(
            "scouting_summary",
            "",
        ),
    )

    add_report_footer(
        figure,
        report,
        3,
    )

    return figure


def build_location_page(
    report: dict[str, Any],
    page_number: int,
    pitch_offset: int,
    page_title: str,
) -> Figure:
    """
    Build one landscape location page with three large heatmaps.

    Titles are positioned above each chart by draw_location_panels().
    """
    figure = plt.figure(
        figsize=(
            REPORT_WIDTH,
            REPORT_HEIGHT,
        ),
        facecolor=BACKGROUND_COLOR,
    )

    pitcher_name = report.get(
        "pitcher_name",
        "Unknown Pitcher",
    )
    season = report.get(
        "season",
        "",
    )

    add_section_header(
        figure,
        page_title,
        (
            f"{pitcher_name} | {season} | "
            "Pitch-location density by pitch type"
        ),
    )

    grid = figure.add_gridspec(
        nrows=22,
        ncols=18,
        left=0.055,
        right=0.945,
        top=0.825,
        bottom=0.080,
        hspace=1.20,
        wspace=1.55,
    )

    location_axes = [
        figure.add_subplot(
            grid[0:22, 0:6]
        ),
        figure.add_subplot(
            grid[0:22, 6:12]
        ),
        figure.add_subplot(
            grid[0:22, 12:18]
        ),
    ]

    all_locations = report.get(
        "pitch_locations",
        [],
    )

    location_frame = pd.DataFrame(
        all_locations
    )

    if (
        not location_frame.empty
        and "pitch_type"
        in location_frame.columns
    ):
        ordered_types = (
            location_frame[
                "pitch_type"
            ]
            .value_counts()
            .index
            .astype(str)
            .tolist()
        )

        selected_types = ordered_types[
            pitch_offset:
            pitch_offset + 3
        ]

        selected_locations = (
            location_frame[
                location_frame[
                    "pitch_type"
                ]
                .astype(str)
                .isin(
                    selected_types
                )
            ]
            .to_dict(
                "records"
            )
        )

    else:
        selected_locations = []

    draw_location_panels(
        axes=location_axes,
        pitch_locations=(
            selected_locations
        ),
        top_n=3,
    )

    add_report_footer(
        figure,
        report,
        page_number,
    )

    return figure


def build_page_one(
    report: dict[str, Any],
) -> Figure:
    """Backward-compatible page-one alias."""
    return build_overview_page(
        report
    )


def build_page_two(
    report: dict[str, Any],
) -> Figure:
    """Backward-compatible page-two alias."""
    return build_arsenal_page(
        report
    )


def build_page_three(
    report: dict[str, Any],
) -> Figure:
    """Backward-compatible page-three alias."""
    return build_characteristics_page(
        report
    )


def create_one_page_preview(
    report: dict[str, Any],
) -> Figure:
    """
    Create a landscape overview image.

    The complete report should be exported as PDF.
    """
    return build_overview_page(
        report
    )


# =============================================================================
# PUBLIC EXPORT FUNCTION
# =============================================================================

def create_pitcher_report_card(
    report: dict[str, Any],
    output_path: str | Path,
    dpi: int = 220,
    show: bool = False,
) -> Path:
    """
    Export a five-page landscape pitcher report.

    PDF pages:
        1. Scouting overview
        2. Pitch arsenal and usage
        3. Pitch characteristics, splits, and summary
        4. Primary pitch locations
        5. Secondary pitch locations

    PNG/JPG:
        Landscape scouting-overview preview.
    """
    report = normalize_report(
        report
    )

    output = Path(
        output_path
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    suffix = output.suffix.lower()

    if suffix == ".pdf":
        figures = [
            build_overview_page(
                report
            ),
            build_arsenal_page(
                report
            ),
            build_characteristics_page(
                report
            ),
            build_location_page(
                report=report,
                page_number=4,
                pitch_offset=0,
                page_title=(
                    "Primary Pitch Locations"
                ),
            ),
            build_location_page(
                report=report,
                page_number=5,
                pitch_offset=3,
                page_title=(
                    "Secondary Pitch Locations"
                ),
            ),
        ]

        with PdfPages(
            output
        ) as pdf:
            for figure in figures:
                pdf.savefig(
                    figure,
                    dpi=dpi,
                    facecolor=(
                        figure.get_facecolor()
                    ),
                    bbox_inches=None,
                    pad_inches=0.03,
                )

                if show:
                    figure.show()

                plt.close(
                    figure
                )

        return output

    figure = create_one_page_preview(
        report
    )

    figure.savefig(
        output,
        dpi=dpi,
        facecolor=(
            figure.get_facecolor()
        ),
        bbox_inches=None,
        pad_inches=0.03,
    )

    if show:
        plt.show()

    plt.close(
        figure
    )

    return output
