from __future__ import annotations
from typing import Any
import pandas as pd

# CONSTANTS
PITCH_NAMES = {
    "FF": "Four-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "FA": "Fastball",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Forkball",
    "SL": "Slider",
    "ST": "Sweeper",
    "CU": "Curveball",
    "KC": "Knuckle Curve",
    "SV": "Slurve",
    "KN": "Knuckleball",
    "EP": "Eephus",
    "SC": "Screwball",
    "PO": "Pitchout",
}

GRADE_ORDER = [
    "overall",
    "stuff",
    "command",
    "bat_missing",
    "contact_management",
    "arsenal",
]

GRADE_DISPLAY_NAMES = {
    "overall": "Overall",
    "stuff": "Stuff",
    "command": "Command",
    "bat_missing": "Bat Missing",
    "contact_management": "Contact Management",
    "arsenal": "Arsenal",
}

SUMMARY_DISPLAY_NAMES = {
    "pitch_count": "Pitches",
    "game_count": "Games",
    "batter_count": "Batters Faced",
    "plate_appearances": "Plate Appearances",
    "strike_rate": "Strike Rate",
    "swing_rate": "Swing Rate",
    "whiff_rate": "Whiff Rate",
    "csw_rate": "CSW Rate",
    "zone_rate": "Zone Rate",
    "chase_rate": "Chase Rate",
    "contact_rate": "Contact Rate",
    "average_velocity": "Average Velocity",
    "average_spin_rate": "Average Spin Rate",
    "average_extension": "Average Extension",
    "average_exit_velocity": "Average Exit Velocity",
    "hard_hit_rate": "Hard-Hit Rate",
    "sweet_spot_rate": "Sweet-Spot Rate",
    "expected_woba_allowed": "xwOBA Allowed",
    "expected_slugging_allowed": "xSLG Allowed",
}

PERCENTAGE_METRICS = {
    "strike_rate",
    "swing_rate",
    "whiff_rate",
    "csw_rate",
    "zone_rate",
    "chase_rate",
    "contact_rate",
    "hard_hit_rate",
    "sweet_spot_rate",
}

INTEGER_METRICS = {
    "pitch_count",
    "game_count",
    "batter_count",
    "plate_appearances",
}

DECIMAL_METRICS = {
    "expected_woba_allowed",
    "expected_slugging_allowed",
}

# SAFE VALUE HELPERS
def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value into a float safely.
    """
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Convert a value into an integer safely.
    """
    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def json_safe_value(
    value: Any,
) -> Any:
    """
    Convert pandas and NumPy values into standard
    Python values that can be serialized to JSON.
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    return value


def clean_dictionary(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert all values in a dictionary into
    JSON-safe Python values.
    """
    return {
        key: json_safe_value(value)
        for key, value in record.items()
    }

# FORMATTING HELPERS

def get_pitch_name(
    pitch_type: str | None,
) -> str:
    """
    Convert an MLB pitch code into a display name.
    """
    if not pitch_type:
        return "Unknown Pitch"

    return PITCH_NAMES.get(
        pitch_type,
        pitch_type,
    )


def format_metric_value(
    metric_name: str,
    value: Any,
) -> str:
    """
    Format a summary metric for website display.
    """
    if value is None:
        return "N/A"

    if metric_name in INTEGER_METRICS:
        return f"{safe_int(value):,}"

    if metric_name in PERCENTAGE_METRICS:
        return f"{safe_float(value):.1f}%"

    if metric_name == "average_velocity":
        return f"{safe_float(value):.1f} mph"

    if metric_name == "average_spin_rate":
        return f"{safe_float(value):.0f} rpm"

    if metric_name == "average_extension":
        return f"{safe_float(value):.1f} ft"

    if metric_name == "average_exit_velocity":
        return f"{safe_float(value):.1f} mph"

    if metric_name in DECIMAL_METRICS:
        return f"{safe_float(value):.3f}"

    return str(value)


def get_grade_color_group(
    grade: int,
) -> str:
    """
    Return a semantic display category.

    The website can map these categories to actual colors.
    """
    if grade >= 70:
        return "elite"

    if grade >= 60:
        return "plus"

    if grade >= 55:
        return "above_average"

    if grade >= 50:
        return "average"

    if grade >= 45:
        return "fringe"

    if grade >= 40:
        return "below_average"

    return "poor"


# Header

def build_header(
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the player identity section.
    """
    identity = profile.get("identity", {})
    classification = profile.get("classification") or {}

    pitcher_name = (
        identity.get("pitcher_name")
        or "Unknown Pitcher"
    )

    throws = identity.get("throws")

    throws_display = None

    if throws == "R":
        throws_display = "Right-Handed"

    elif throws == "L":
        throws_display = "Left-Handed"

    elif throws:
        throws_display = str(throws)

    return {
        "pitcher_id": identity.get("pitcher_id"),
        "pitcher_name": pitcher_name,
        "throws": throws,
        "throws_display": throws_display,
        "season": identity.get("season"),
        "pitcher_type": classification.get(
            "pitcher_type"
        ),
        "subtitle": (
            f"{throws_display} Pitcher"
            if throws_display
            else "Pitcher"
        ),
    }


# Grade Card
def build_grade_cards(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build an ordered list of scouting-grade cards.
    """
    grade_profile = profile.get("grades", {})
    grades = grade_profile.get("grades", {})

    grade_cards: list[dict[str, Any]] = []

    for grade_key in GRADE_ORDER:
        grade_result = grades.get(grade_key)

        if not grade_result:
            continue

        grade_value = safe_int(
            grade_result.get("grade"),
            default=50,
        )

        grade_cards.append(
            {
                "key": grade_key,
                "name": GRADE_DISPLAY_NAMES.get(
                    grade_key,
                    grade_key.replace("_", " ").title(),
                ),
                "grade": grade_value,
                "label": grade_result.get(
                    "label",
                    "Average",
                ),
                "color_group": get_grade_color_group(
                    grade_value
                ),
                "is_overall": grade_key == "overall",
            }
        )

    return grade_cards

def build_radar_chart(
    profile: dict[str, Any],
) -> dict[str, list[Any]]:
    """
    Build radar-chart data from category grades.

    Overall is excluded because it is the combined grade.
    """
    grade_profile = profile.get("grades", {})
    grades = grade_profile.get("grades", {})

    radar_keys = [
        "stuff",
        "command",
        "bat_missing",
        "contact_management",
        "arsenal",
    ]

    labels: list[str] = []
    values: list[int] = []

    for grade_key in radar_keys:
        result = grades.get(grade_key)

        if not result:
            continue

        labels.append(
            GRADE_DISPLAY_NAMES.get(
                grade_key,
                grade_key.replace("_", " ").title(),
            )
        )

        values.append(
            safe_int(
                result.get("grade"),
                default=50,
            )
        )

    return {
        "labels": labels,
        "values": values,
        "minimum": 20,
        "maximum": 80,
        "average": 50,
    }

# Summary
def build_summary_cards(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build formatted overall metric cards.
    """
    summary = profile.get("summary", {})

    display_order = [
        "pitch_count",
        "game_count",
        "plate_appearances",
        "strike_rate",
        "whiff_rate",
        "csw_rate",
        "zone_rate",
        "chase_rate",
        "contact_rate",
        "average_velocity",
        "average_spin_rate",
        "average_extension",
        "average_exit_velocity",
        "hard_hit_rate",
        "expected_woba_allowed",
        "expected_slugging_allowed",
    ]

    cards: list[dict[str, Any]] = []

    for metric_name in display_order:
        if metric_name not in summary:
            continue

        raw_value = summary.get(metric_name)

        cards.append(
            {
                "key": metric_name,
                "name": SUMMARY_DISPLAY_NAMES.get(
                    metric_name,
                    metric_name.replace("_", " ").title(),
                ),
                "value": json_safe_value(raw_value),
                "display_value": format_metric_value(
                    metric_name,
                    raw_value,
                ),
            }
        )

    return cards

# PITCH ARSENAL
def find_pitch_grade(
    profile: dict[str, Any],
    pitch_type: str,
) -> dict[str, Any] | None:
    """
    Find the grading record for a pitch type.
    """
    pitch_grades = (
        profile
        .get("grades", {})
        .get("pitch_grades", [])
    )

    for pitch_grade in pitch_grades:
        if pitch_grade.get("pitch_type") == pitch_type:
            return pitch_grade

    return None


def build_arsenal_table(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build the website-ready pitch arsenal table.
    """
    arsenal = profile.get("arsenal", [])

    rows: list[dict[str, Any]] = []

    sorted_arsenal = sorted(
        arsenal,
        key=lambda pitch: (
            safe_float(
                pitch.get("usage_percent")
            ),
            safe_int(
                pitch.get("pitch_count")
            ),
        ),
        reverse=True,
    )

    for pitch in sorted_arsenal:
        pitch_type = pitch.get("pitch_type")
        pitch_grade = find_pitch_grade(
            profile,
            pitch_type,
        )

        overall_grade = None
        grade_label = None
        color_group = None

        if pitch_grade:
            overall_grade = safe_int(
                pitch_grade.get(
                    "overall_pitch_grade"
                )
            )

            color_group = get_grade_color_group(
                overall_grade
            )

            grade_label = get_pitch_grade_label(
                overall_grade
            )

        rows.append(
            {
                "pitch_type": pitch_type,
                "pitch_name": get_pitch_name(
                    pitch_type
                ),
                "pitch_count": safe_int(
                    pitch.get("pitch_count")
                ),
                "usage_percent": safe_float(
                    pitch.get("usage_percent")
                ),
                "average_velocity": safe_float(
                    pitch.get("average_velocity")
                ),
                "maximum_velocity": safe_float(
                    pitch.get("maximum_velocity")
                ),
                "average_spin_rate": safe_float(
                    pitch.get("average_spin_rate")
                ),
                "average_extension": safe_float(
                    pitch.get("average_extension")
                ),
                "strike_rate": safe_float(
                    pitch.get("strike_rate")
                ),
                "zone_rate": safe_float(
                    pitch.get("zone_rate")
                ),
                "swing_rate": safe_float(
                    pitch.get("swing_rate")
                ),
                "whiff_rate": safe_float(
                    pitch.get("whiff_rate")
                ),
                "csw_rate": safe_float(
                    pitch.get("csw_rate")
                ),
                "chase_rate": safe_float(
                    pitch.get("chase_rate")
                ),
                "average_exit_velocity": safe_float(
                    pitch.get(
                        "average_exit_velocity"
                    )
                ),
                "hard_hit_rate": safe_float(
                    pitch.get("hard_hit_rate")
                ),
                "expected_woba_allowed": safe_float(
                    pitch.get(
                        "expected_woba_allowed"
                    )
                ),
                "expected_slugging_allowed": safe_float(
                    pitch.get(
                        "expected_slugging_allowed"
                    )
                ),
                "overall_pitch_grade": overall_grade,
                "pitch_grade_label": grade_label,
                "color_group": color_group,
            }
        )

    return rows

def get_pitch_grade_label(
    grade: int,
) -> str:
    """
    Return a compact grade label for a pitch.
    """
    if grade >= 70:
        return "Plus-Plus"

    if grade >= 60:
        return "Plus"

    if grade >= 55:
        return "Above Average"

    if grade >= 50:
        return "Average"

    if grade >= 45:
        return "Fringe Average"

    if grade >= 40:
        return "Below Average"

    return "Poor"

def build_arsenal_chart(
    profile: dict[str, Any],
) -> dict[str, list[Any]]:
    """
    Build chart-ready usage and pitch-grade data.
    """
    arsenal_rows = build_arsenal_table(profile)

    return {
        "pitch_types": [
            row["pitch_type"]
            for row in arsenal_rows
        ],
        "pitch_names": [
            row["pitch_name"]
            for row in arsenal_rows
        ],
        "usage_percentages": [
            row["usage_percent"]
            for row in arsenal_rows
        ],
        "pitch_grades": [
            row["overall_pitch_grade"]
            for row in arsenal_rows
        ],
        "velocities": [
            row["average_velocity"]
            for row in arsenal_rows
        ],
    }

# HIGHLIGHTS
def format_highlight_pitch(
    pitch: dict[str, Any] | None,
    highlight_type: str,
) -> dict[str, Any] | None:
    """
    Format one highlighted pitch.
    """
    if not pitch:
        return None

    pitch_type = pitch.get("pitch_type")

    highlight = {
        "pitch_type": pitch_type,
        "pitch_name": get_pitch_name(pitch_type),
        "pitch_count": safe_int(
            pitch.get("pitch_count")
        ),
        "usage_percent": safe_float(
            pitch.get("usage_percent")
        ),
        "average_velocity": safe_float(
            pitch.get("average_velocity")
        ),
    }

    if highlight_type == "primary":
        highlight.update(
            {
                "metric_name": "Usage",
                "metric_value": safe_float(
                    pitch.get("usage_percent")
                ),
                "display_value": (
                    f"{safe_float(pitch.get('usage_percent')):.1f}%"
                ),
            }
        )

    elif highlight_type == "whiff":
        highlight.update(
            {
                "metric_name": "Whiff Rate",
                "metric_value": safe_float(
                    pitch.get("whiff_rate")
                ),
                "display_value": (
                    f"{safe_float(pitch.get('whiff_rate')):.1f}%"
                ),
            }
        )

    elif highlight_type == "chase":
        highlight.update(
            {
                "metric_name": "Chase Rate",
                "metric_value": safe_float(
                    pitch.get("chase_rate")
                ),
                "display_value": (
                    f"{safe_float(pitch.get('chase_rate')):.1f}%"
                ),
            }
        )

    elif highlight_type == "strike":
        highlight.update(
            {
                "metric_name": "Strike Rate",
                "metric_value": safe_float(
                    pitch.get("strike_rate")
                ),
                "display_value": (
                    f"{safe_float(pitch.get('strike_rate')):.1f}%"
                ),
            }
        )

    return highlight

def build_highlights(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Build the primary pitch and best-pitch cards.
    """
    highlights = profile.get("highlights", {})

    highlight_definitions = [
        (
            "primary_pitch",
            "Primary Pitch",
            "primary",
        ),
        (
            "best_whiff_pitch",
            "Best Swing-and-Miss Pitch",
            "whiff",
        ),
        (
            "best_chase_pitch",
            "Best Chase Pitch",
            "chase",
        ),
        (
            "best_strike_pitch",
            "Best Strike Pitch",
            "strike",
        ),
    ]

    output: list[dict[str, Any]] = []

    for profile_key, title, highlight_type in (
        highlight_definitions
    ):
        formatted = format_highlight_pitch(
            highlights.get(profile_key),
            highlight_type,
        )

        if not formatted:
            continue

        formatted["key"] = profile_key
        formatted["title"] = title

        output.append(formatted)

    return output

# CLASSIFICATIONS
def build_classification_cards(
    profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Format pitcher classifications for display.
    """
    classification = profile.get("classification") or {}

    classification_order = [
        (
            "velocity_profile",
            "Velocity Profile",
        ),
        (
            "command_profile",
            "Command Profile",
        ),
        (
            "bat_missing_profile",
            "Bat-Missing Profile",
        ),
        (
            "chase_profile",
            "Chase Profile",
        ),
        (
            "contact_profile",
            "Contact Profile",
        ),
        (
            "arsenal_shape",
            "Arsenal Shape",
        ),
    ]

    cards: list[dict[str, Any]] = []

    for key, display_name in classification_order:
        value = classification.get(key)

        if not value:
            continue

        cards.append(
            {
                "key": key,
                "name": display_name,
                "value": value,
            }
        )

    return cards

# COMPLETE REPORT
def build_pitcher_report(
    profile: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert a pitcher profile into a clean,
    website-ready scouting report.
    """
    header = build_header(profile)
    grade_cards = build_grade_cards(profile)

    overall_grade = next(
        (
            grade
            for grade in grade_cards
            if grade["is_overall"]
        ),
        None,
    )

    return {
        "report_type": "pitcher_scouting_report",
        "header": header,
        "overall_grade": overall_grade,
        "grade_cards": grade_cards,
        "radar_chart": build_radar_chart(profile),
        "summary_cards": build_summary_cards(profile),
        "classification_cards": (
            build_classification_cards(profile)
        ),
        "highlights": build_highlights(profile),
        "arsenal_table": build_arsenal_table(profile),
        "arsenal_chart": build_arsenal_chart(profile),
        "strengths": list(
            profile.get("strengths", [])
        ),
        "concerns": list(
            profile.get("concerns", [])
        ),
        "scouting_summary": profile.get(
            "scouting_summary"
        ),
        "metadata": {
            "season": header.get("season"),
            "pitcher_id": header.get("pitcher_id"),
            "pitch_count": safe_int(
                profile
                .get("summary", {})
                .get("pitch_count")
            ),
        },
    }