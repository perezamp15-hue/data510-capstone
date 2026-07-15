from __future__ import annotations
import math
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

# Statcast velocity and acceleration measurements are based around y = 50 feet.
STATCAST_Y_START = 50.0

# Approximate front edge of home plate, measured from the back point.
PLATE_Y = 17.0 / 12.0

# Gravity in feet per second squared.
GRAVITY_FTPS2 = 32.174

# Typical horizontal and vertical plotting limits for pitch-location charts.
LOCATION_X_LIMITS = (-2.5, 2.5)
LOCATION_Z_LIMITS = (0.0, 5.0)

# Approximate rule-book strike-zone width.
STRIKE_ZONE_LEFT = -17.0 / 24.0
STRIKE_ZONE_RIGHT = 17.0 / 24.0


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
    "SC": "Screwball",
    "KN": "Knuckleball",
    "EP": "Eephus",
}


# VALIDATION HELPERS

def require_columns(
    dataframe: pd.DataFrame,
    required_columns: list[str],
) -> None:
    """
    Raise a clear error when required Statcast columns are missing.
    """
    missing = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing:
        raise ValueError(
            "The pitch dataframe is missing required columns: "
            + ", ".join(missing)
        )


def numeric_series(
    dataframe: pd.DataFrame,
    column: str,
) -> pd.Series:
    """
    Convert a dataframe column to numeric values.
    Invalid values become NaN.
    """
    return pd.to_numeric(dataframe[column], errors="coerce")


# MOVEMENT CALCULATION

def solve_flight_time(
    vy0: float,
    ay: float,
    start_y: float = STATCAST_Y_START,
    target_y: float = PLATE_Y,
) -> Optional[float]:
    """
    Calculate the time required for a pitch to travel from the Statcast
    measurement plane to home plate.

    Equation:

        target_y = start_y + vy0*t + 0.5*ay*t^2

    Parameters
    ----------
    vy0:
        Initial velocity in the y direction, in feet per second.
        This will normally be negative because the pitch travels toward home.

    ay:
        Acceleration in the y direction, in feet per second squared.

    start_y:
        Starting y-coordinate. Statcast velocity fields are commonly measured
        at approximately y = 50 feet.

    target_y:
        Target y-coordinate near the front of home plate.

    Returns
    -------
    float | None
        Flight time in seconds, or None if no realistic solution exists.
    """
    values = [vy0, ay, start_y, target_y]

    if not all(math.isfinite(float(value)) for value in values):
        return None

    a = 0.5 * float(ay)
    b = float(vy0)
    c = float(start_y) - float(target_y)

    # Handle a nearly linear equation.
    if abs(a) < 1e-10:
        if abs(b) < 1e-10:
            return None

        time_value = -c / b

        if 0.20 <= time_value <= 0.70:
            return time_value

        return None

    discriminant = (b * b) - (4.0 * a * c)

    if discriminant < 0:
        return None

    square_root = math.sqrt(discriminant)

    roots = [
        (-b + square_root) / (2.0 * a),
        (-b - square_root) / (2.0 * a),
    ]

    realistic_roots = [
        root
        for root in roots
        if math.isfinite(root) and 0.20 <= root <= 0.70
    ]

    if not realistic_roots:
        return None

    return min(realistic_roots)


def estimate_single_pitch_movement(
    vy0: float,
    ax: float,
    ay: float,
    az: float,
    horizontal_sign: float = 1.0,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Estimate pitch movement in inches.

    Horizontal break is estimated as the horizontal displacement created by
    horizontal acceleration:

        horizontal_break = 0.5 * ax * t^2

    Induced vertical break compares the actual vertical acceleration with a
    gravity-only trajectory:

        induced_vertical_break = 0.5 * (az + gravity) * t^2

    Statcast acceleration values include gravity, so adding positive gravity
    removes the gravity-only component.

    Parameters
    ----------
    horizontal_sign:
        Leave as 1.0 initially. Change to -1.0 only if validation against a
        trusted Statcast sample shows your horizontal direction is reversed.

    Returns
    -------
    tuple
        horizontal break in inches,
        induced vertical break in inches,
        flight time in seconds.
    """
    flight_time = solve_flight_time(
        vy0=vy0,
        ay=ay,
    )

    if flight_time is None:
        return None, None, None

    horizontal_break_feet = (
        0.5
        * float(ax)
        * flight_time**2
        * horizontal_sign
    )

    induced_vertical_break_feet = (
        0.5
        * (float(az) + GRAVITY_FTPS2)
        * flight_time**2
    )

    horizontal_break_inches = horizontal_break_feet * 12.0
    induced_vertical_break_inches = induced_vertical_break_feet * 12.0

    # Remove physically unreasonable results caused by corrupt records.
    if not -35.0 <= horizontal_break_inches <= 35.0:
        horizontal_break_inches = None

    if not -35.0 <= induced_vertical_break_inches <= 35.0:
        induced_vertical_break_inches = None

    return (
        horizontal_break_inches,
        induced_vertical_break_inches,
        flight_time,
    )


def calculate_pitch_movement(
    pitches: pd.DataFrame,
    horizontal_sign: float = 1.0,
) -> pd.DataFrame:
    """
    Calculate estimated movement for each individual pitch.

    The original dataframe is not changed.
    """
    required_columns = [
        "pitch_type",
        "vy0",
        "ax",
        "ay",
        "az",
    ]

    require_columns(
        dataframe=pitches,
        required_columns=required_columns,
    )

    movement_pitches = pitches.copy()

    for column in ["vy0", "ax", "ay", "az"]:
        movement_pitches[column] = numeric_series(
            movement_pitches,
            column,
        )

    horizontal_values: list[Optional[float]] = []
    vertical_values: list[Optional[float]] = []
    flight_times: list[Optional[float]] = []

    for pitch in movement_pitches.itertuples(index=False):
        horizontal_break, vertical_break, flight_time = (
            estimate_single_pitch_movement(
                vy0=getattr(pitch, "vy0"),
                ax=getattr(pitch, "ax"),
                ay=getattr(pitch, "ay"),
                az=getattr(pitch, "az"),
                horizontal_sign=horizontal_sign,
            )
        )

        horizontal_values.append(horizontal_break)
        vertical_values.append(vertical_break)
        flight_times.append(flight_time)

    movement_pitches["estimated_horizontal_break"] = horizontal_values
    movement_pitches["estimated_vertical_break"] = vertical_values
    movement_pitches["estimated_flight_time"] = flight_times

    movement_pitches = movement_pitches.dropna(
        subset=[
            "pitch_type",
            "estimated_horizontal_break",
            "estimated_vertical_break",
        ]
    )

    return movement_pitches


def summarize_pitch_movement(
    movement_pitches: pd.DataFrame,
    minimum_pitch_count: int = 5,
) -> pd.DataFrame:
    """
    Create one movement-summary row per pitch type.
    """
    require_columns(
        dataframe=movement_pitches,
        required_columns=[
            "pitch_type",
            "estimated_horizontal_break",
            "estimated_vertical_break",
        ],
    )

    aggregation: dict[str, tuple[str, str]] = {
        "pitch_count": (
            "pitch_type",
            "size",
        ),
        "horizontal_break": (
            "estimated_horizontal_break",
            "mean",
        ),
        "vertical_break": (
            "estimated_vertical_break",
            "mean",
        ),
        "horizontal_break_std": (
            "estimated_horizontal_break",
            "std",
        ),
        "vertical_break_std": (
            "estimated_vertical_break",
            "std",
        ),
    }

    if "release_velocity" in movement_pitches.columns:
        movement_pitches = movement_pitches.copy()
        movement_pitches["release_velocity"] = numeric_series(
            movement_pitches,
            "release_velocity",
        )

        aggregation["average_velocity"] = (
            "release_velocity",
            "mean",
        )

    summary = (
        movement_pitches
        .groupby("pitch_type", as_index=False)
        .agg(**aggregation)
    )

    summary = summary[
        summary["pitch_count"] >= minimum_pitch_count
    ].copy()

    total_pitches = summary["pitch_count"].sum()

    if total_pitches > 0:
        summary["usage_percentage"] = (
            summary["pitch_count"]
            / total_pitches
            * 100.0
        )
    else:
        summary["usage_percentage"] = 0.0

    summary["pitch_name"] = summary["pitch_type"].map(
        PITCH_NAMES
    ).fillna(summary["pitch_type"])

    summary = summary.sort_values(
        by="pitch_count",
        ascending=False,
    ).reset_index(drop=True)

    numeric_columns = [
        "horizontal_break",
        "vertical_break",
        "horizontal_break_std",
        "vertical_break_std",
        "usage_percentage",
    ]

    if "average_velocity" in summary.columns:
        numeric_columns.append("average_velocity")

    summary[numeric_columns] = summary[numeric_columns].round(1)

    return summary


# LOCATION DATA

def prepare_location_data(
    pitches: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean pitch-location coordinates.
    """
    required_columns = [
        "pitch_type",
        "plate_crossing_x",
        "plate_crossing_z",
    ]

    require_columns(
        dataframe=pitches,
        required_columns=required_columns,
    )

    locations = pitches.copy()

    locations["plate_crossing_x"] = numeric_series(
        locations,
        "plate_crossing_x",
    )

    locations["plate_crossing_z"] = numeric_series(
        locations,
        "plate_crossing_z",
    )

    locations = locations.dropna(
        subset=[
            "pitch_type",
            "plate_crossing_x",
            "plate_crossing_z",
        ]
    )

    # Remove obvious tracking errors and extreme pitchouts.
    locations = locations[
        locations["plate_crossing_x"].between(-5.0, 5.0)
        & locations["plate_crossing_z"].between(-2.0, 8.0)
    ].copy()

    return locations


def get_top_pitch_types(
    locations: pd.DataFrame,
    top_n: int = 3,
    minimum_pitch_count: int = 10,
) -> list[str]:
    """
    Return the most frequently thrown pitch types.
    """
    counts = locations["pitch_type"].value_counts()

    counts = counts[counts >= minimum_pitch_count]

    return counts.head(top_n).index.tolist()


# PLOTTING HELPERS

def draw_strike_zone(
    axis: Axes,
    zone_bottom: float = 1.5,
    zone_top: float = 3.5,
) -> None:
    """
    Draw a standard strike-zone rectangle.
    """
    zone = Rectangle(
        (STRIKE_ZONE_LEFT, zone_bottom),
        STRIKE_ZONE_RIGHT - STRIKE_ZONE_LEFT,
        zone_top - zone_bottom,
        fill=False,
        linewidth=1.5,
        edgecolor="black",
        zorder=10,
    )

    axis.add_patch(zone)

    # Add nine-zone divisions.
    width = STRIKE_ZONE_RIGHT - STRIKE_ZONE_LEFT
    height = zone_top - zone_bottom

    for fraction in (1.0 / 3.0, 2.0 / 3.0):
        x_value = STRIKE_ZONE_LEFT + width * fraction
        axis.plot(
            [x_value, x_value],
            [zone_bottom, zone_top],
            linewidth=0.6,
            alpha=0.55,
            color="black",
            zorder=10,
        )

        z_value = zone_bottom + height * fraction
        axis.plot(
            [STRIKE_ZONE_LEFT, STRIKE_ZONE_RIGHT],
            [z_value, z_value],
            linewidth=0.6,
            alpha=0.55,
            color="black",
            zorder=10,
        )


def calculate_pitcher_strike_zone(
    pitch_data: pd.DataFrame,
) -> tuple[float, float]:
    """
    Use batter-specific Statcast zone boundaries when available.
    Otherwise return reasonable default values.
    """
    default_bottom = 1.5
    default_top = 3.5

    if (
        "sz_bottom" not in pitch_data.columns
        or "sz_top" not in pitch_data.columns
    ):
        return default_bottom, default_top

    bottom_values = numeric_series(
        pitch_data,
        "sz_bottom",
    ).dropna()

    top_values = numeric_series(
        pitch_data,
        "sz_top",
    ).dropna()

    if bottom_values.empty or top_values.empty:
        return default_bottom, default_top

    zone_bottom = float(bottom_values.median())
    zone_top = float(top_values.median())

    if not 0.5 <= zone_bottom <= 2.5:
        zone_bottom = default_bottom

    if not 2.5 <= zone_top <= 5.0:
        zone_top = default_top

    if zone_top <= zone_bottom:
        return default_bottom, default_top

    return zone_bottom, zone_top


def draw_pitch_location_heatmap(
    axis: Axes,
    pitch_data: pd.DataFrame,
    pitch_type: str,
    bins: int = 35,
) -> None:
    """
    Draw a two-dimensional pitch-location heatmap for one pitch type.
    """
    selected = pitch_data[
        pitch_data["pitch_type"] == pitch_type
    ].copy()

    pitch_count = len(selected)

    if selected.empty:
        axis.text(
            0.5,
            0.5,
            f"No {pitch_type} locations",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )

        axis.set_axis_off()
        return

    x_values = selected["plate_crossing_x"].to_numpy()
    z_values = selected["plate_crossing_z"].to_numpy()

    heatmap, x_edges, z_edges = np.histogram2d(
        x_values,
        z_values,
        bins=bins,
        range=[
            list(LOCATION_X_LIMITS),
            list(LOCATION_Z_LIMITS),
        ],
    )

    # Smooth the heatmap when SciPy is installed.
    try:
        from scipy.ndimage import gaussian_filter

        heatmap = gaussian_filter(
            heatmap,
            sigma=1.25,
        )
    except ImportError:
        pass

    axis.imshow(
        heatmap.T,
        origin="lower",
        extent=[
            LOCATION_X_LIMITS[0],
            LOCATION_X_LIMITS[1],
            LOCATION_Z_LIMITS[0],
            LOCATION_Z_LIMITS[1],
        ],
        aspect="auto",
        interpolation="bilinear",
        cmap="YlOrRd",
    )

    zone_bottom, zone_top = calculate_pitcher_strike_zone(
        selected
    )

    draw_strike_zone(
        axis=axis,
        zone_bottom=zone_bottom,
        zone_top=zone_top,
    )

    pitch_name = PITCH_NAMES.get(
        pitch_type,
        pitch_type,
    )

    axis.set_title(
        f"{pitch_name}\n{pitch_count:,} pitches",
        fontsize=10,
        fontweight="bold",
    )

    axis.set_xlim(*LOCATION_X_LIMITS)
    axis.set_ylim(*LOCATION_Z_LIMITS)

    axis.set_xlabel(
        "Horizontal location (ft)",
        fontsize=8,
    )

    axis.set_ylabel(
        "Height (ft)",
        fontsize=8,
    )

    axis.tick_params(
        axis="both",
        labelsize=7,
    )

    axis.axvline(
        0,
        linewidth=0.5,
        alpha=0.35,
        color="black",
    )


def draw_movement_profile(
    axis: Axes,
    movement_summary: pd.DataFrame,
) -> None:
    """
    Draw one point for each pitch type on a movement plot.
    """
    if movement_summary.empty:
        axis.text(
            0.5,
            0.5,
            "Movement data is unavailable",
            ha="center",
            va="center",
            transform=axis.transAxes,
        )

        axis.set_axis_off()
        return

    x_values = movement_summary["horizontal_break"]
    y_values = movement_summary["vertical_break"]

    usage_values = movement_summary["usage_percentage"].fillna(0)

    marker_sizes = 70 + usage_values * 9

    axis.scatter(
        x_values,
        y_values,
        s=marker_sizes,
        alpha=0.80,
        edgecolors="black",
        linewidths=0.8,
    )

    for row in movement_summary.itertuples(index=False):
        label = str(row.pitch_type)

        if hasattr(row, "average_velocity") and pd.notna(
            row.average_velocity
        ):
            label = (
                f"{row.pitch_type}\n"
                f"{row.average_velocity:.1f} mph"
            )

        axis.annotate(
            label,
            (
                row.horizontal_break,
                row.vertical_break,
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            fontweight="bold",
        )

    axis.axhline(
        0,
        linewidth=0.8,
        alpha=0.5,
        color="black",
    )

    axis.axvline(
        0,
        linewidth=0.8,
        alpha=0.5,
        color="black",
    )

    x_padding = 3.0
    y_padding = 3.0

    axis.set_xlim(
        min(-5.0, float(x_values.min()) - x_padding),
        max(5.0, float(x_values.max()) + x_padding),
    )

    axis.set_ylim(
        min(-5.0, float(y_values.min()) - y_padding),
        max(5.0, float(y_values.max()) + y_padding),
    )

    axis.set_title(
        "Estimated Pitch Movement",
        fontsize=12,
        fontweight="bold",
    )

    axis.set_xlabel(
        "Horizontal break (inches)",
        fontsize=9,
    )

    axis.set_ylabel(
        "Induced vertical break (inches)",
        fontsize=9,
    )

    axis.grid(
        alpha=0.20,
        linewidth=0.6,
    )

    axis.text(
        0.99,
        0.01,
        "Bubble size represents usage",
        ha="right",
        va="bottom",
        transform=axis.transAxes,
        fontsize=7,
        alpha=0.65,
    )


# FULL FIGURE

def create_pitch_location_movement_figure(
    pitches: pd.DataFrame,
    output_path: str | Path,
    pitcher_name: str = "Pitcher",
    season: Optional[int] = None,
    top_n_locations: int = 3,
    horizontal_sign: float = 1.0,
) -> dict[str, object]:
    """
    Create a standalone scouting visualization containing:

    1. Combined pitch-movement profile
    2. Heatmaps for the three most-used pitch types

    Returns cleaned movement data and summary data so they can be reused
    elsewhere in the scouting report.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    movement_pitches = calculate_pitch_movement(
        pitches=pitches,
        horizontal_sign=horizontal_sign,
    )

    movement_summary = summarize_pitch_movement(
        movement_pitches=movement_pitches,
        minimum_pitch_count=5,
    )

    location_data = prepare_location_data(
        pitches=pitches,
    )

    top_pitch_types = get_top_pitch_types(
        locations=location_data,
        top_n=top_n_locations,
        minimum_pitch_count=10,
    )

    figure = plt.figure(
        figsize=(14, 8.5),
        constrained_layout=False,
    )

    grid = figure.add_gridspec(
        nrows=2,
        ncols=6,
        height_ratios=[1.12, 1.0],
        hspace=0.35,
        wspace=0.65,
        top=0.88,
        bottom=0.08,
        left=0.07,
        right=0.97,
    )

    movement_axis = figure.add_subplot(
        grid[0, 1:5]
    )

    draw_movement_profile(
        axis=movement_axis,
        movement_summary=movement_summary,
    )

    location_axes: list[Axes] = []

    if len(top_pitch_types) == 1:
        location_axes = [
            figure.add_subplot(grid[1, 2:4])
        ]
    elif len(top_pitch_types) == 2:
        location_axes = [
            figure.add_subplot(grid[1, 1:3]),
            figure.add_subplot(grid[1, 3:5]),
        ]
    else:
        location_axes = [
            figure.add_subplot(grid[1, 0:2]),
            figure.add_subplot(grid[1, 2:4]),
            figure.add_subplot(grid[1, 4:6]),
        ]

    for axis, pitch_type in zip(
        location_axes,
        top_pitch_types,
    ):
        draw_pitch_location_heatmap(
            axis=axis,
            pitch_data=location_data,
            pitch_type=pitch_type,
        )

    title = f"{pitcher_name} — Pitch Movement and Location"

    if season is not None:
        title += f" ({season})"

    figure.suptitle(
        title,
        fontsize=18,
        fontweight="bold",
        y=0.96,
    )

    figure.text(
        0.5,
        0.91,
        (
            "Movement is estimated from Statcast velocity and acceleration "
            "measurements. Location charts show pitch density at home plate."
        ),
        ha="center",
        va="center",
        fontsize=9,
        alpha=0.70,
    )

    figure.savefig(
        output_path,
        dpi=220,
        bbox_inches="tight",
    )

    plt.close(figure)

    return {
        "movement_pitches": movement_pitches,
        "movement_summary": movement_summary,
        "location_data": location_data,
        "top_pitch_types": top_pitch_types,
        "output_path": str(output_path),
    }


# REPORT-BUILDER HELPERS
def movement_summary_to_records(
    movement_summary: pd.DataFrame,
) -> list[dict]:
    """
    Convert the movement summary into JSON-safe report records.
    """
    if movement_summary.empty:
        return []

    cleaned = movement_summary.replace(
        {
            np.nan: None,
            np.inf: None,
            -np.inf: None,
        }
    )

    return cleaned.to_dict(
        orient="records"
    )


def add_movement_to_arsenal_table(
    arsenal_table: list[dict],
    movement_summary: pd.DataFrame,
) -> list[dict]:
    """
    Merge movement estimates into your existing arsenal-table records.

    Expected arsenal record:

        {
            "pitch_type": "FF",
            "usage_percentage": 39.1,
            "average_velocity": 97.0
        }
    """
    movement_lookup = {
        row.pitch_type: row
        for row in movement_summary.itertuples(index=False)
    }

    updated_arsenal: list[dict] = []

    for original_record in arsenal_table:
        record = dict(original_record)

        pitch_type = record.get("pitch_type")
        movement = movement_lookup.get(pitch_type)

        if movement is not None:
            record["average_horizontal_break"] = float(
                movement.horizontal_break
            )

            record["average_vertical_break"] = float(
                movement.vertical_break
            )

            record["movement_sample_size"] = int(
                movement.pitch_count
            )

        updated_arsenal.append(record)

    return updated_arsenal