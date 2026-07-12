from __future__ import annotations
from typing import Any
import pandas as pd

# GENERIC HELPERS
def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to a float safely.
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


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    """
    Restrict a value to a defined range.
    """
    return max(minimum, min(value, maximum))


def round_to_five(
    value: float,
) -> int:
    """
    Round a scouting grade to the nearest five.
    """
    rounded = int(5 * round(value / 5))

    return int(
        clamp(
            rounded,
            20,
            80,
        )
    )


def linear_grade(
    value: float,
    low_value: float,
    average_value: float,
    high_value: float,
    lower_grade: float = 20,
    average_grade: float = 50,
    upper_grade: float = 80,
) -> int:
    """
    Convert a metric to a 20-80 scouting grade.

    Values below average are interpolated between
    lower_grade and average_grade.

    Values above average are interpolated between
    average_grade and upper_grade.
    """
    value = safe_float(value)

    if value <= average_value:
        denominator = average_value - low_value

        if denominator == 0:
            return round_to_five(average_grade)

        percentage = (
            value - low_value
        ) / denominator

        raw_grade = (
            lower_grade
            + percentage
            * (
                average_grade
                - lower_grade
            )
        )

    else:
        denominator = high_value - average_value

        if denominator == 0:
            return round_to_five(average_grade)

        percentage = (
            value - average_value
        ) / denominator

        raw_grade = (
            average_grade
            + percentage
            * (
                upper_grade
                - average_grade
            )
        )

    return round_to_five(
        clamp(
            raw_grade,
            lower_grade,
            upper_grade,
        )
    )


def inverse_linear_grade(
    value: float,
    elite_value: float,
    average_value: float,
    poor_value: float,
) -> int:
    """
    Grade a metric where lower values are better.

    Examples:
    - hard-hit rate allowed
    - exit velocity allowed
    - xwOBA allowed
    """
    value = safe_float(value)

    if value <= average_value:
        denominator = average_value - elite_value

        if denominator == 0:
            return 50

        percentage = (
            average_value - value
        ) / denominator

        raw_grade = 50 + percentage * 30

    else:
        denominator = poor_value - average_value

        if denominator == 0:
            return 50

        percentage = (
            value - average_value
        ) / denominator

        raw_grade = 50 - percentage * 30

    return round_to_five(
        clamp(
            raw_grade,
            20,
            80,
        )
    )


def weighted_grade(
    grade_weights: list[tuple[int, float]],
) -> int:
    """
    Combine multiple grades using weighted averages.
    """
    if not grade_weights:
        return 50

    total_weight = sum(
        weight
        for _, weight in grade_weights
    )

    if total_weight == 0:
        return 50

    weighted_total = sum(
        grade * weight
        for grade, weight in grade_weights
    )

    return round_to_five(
        weighted_total / total_weight
    )

# INDIVIDUAL METRIC GRADES
def grade_strike_rate(
    strike_rate: float,
) -> int:
    """
    Grade overall strike rate.

    Approximate scale:
    20: 55%
    50: 64%
    80: 72%
    """
    return linear_grade(
        value=strike_rate,
        low_value=55,
        average_value=64,
        high_value=72,
    )


def grade_zone_rate(
    zone_rate: float,
) -> int:
    """
    Grade percentage of pitches thrown in the zone.

    This measures zone attack, not command precision.
    """
    return linear_grade(
        value=zone_rate,
        low_value=32,
        average_value=42,
        high_value=52,
    )


def grade_whiff_rate(
    whiff_rate: float,
) -> int:
    """
    Grade misses per swing.

    Approximate scale:
    20: 12%
    50: 23%
    80: 38%
    """
    return linear_grade(
        value=whiff_rate,
        low_value=12,
        average_value=23,
        high_value=38,
    )


def grade_csw_rate(
    csw_rate: float,
) -> int:
    """
    Grade called strikes plus whiffs per pitch.
    """
    return linear_grade(
        value=csw_rate,
        low_value=20,
        average_value=27,
        high_value=35,
    )


def grade_chase_rate(
    chase_rate: float,
) -> int:
    """
    Grade swings induced outside the strike zone.
    """
    return linear_grade(
        value=chase_rate,
        low_value=20,
        average_value=30,
        high_value=42,
    )


def grade_contact_rate(
    contact_rate: float,
) -> int:
    """
    Lower hitter contact rate is better for the pitcher.
    """
    return inverse_linear_grade(
        value=contact_rate,
        elite_value=60,
        average_value=75,
        poor_value=88,
    )


def grade_hard_hit_rate(
    hard_hit_rate: float,
) -> int:
    """
    Lower hard-hit rate allowed is better.
    """
    return inverse_linear_grade(
        value=hard_hit_rate,
        elite_value=20,
        average_value=35,
        poor_value=50,
    )


def grade_exit_velocity(
    average_exit_velocity: float,
) -> int:
    """
    Lower average exit velocity allowed is better.
    """
    return inverse_linear_grade(
        value=average_exit_velocity,
        elite_value=78,
        average_value=87,
        poor_value=94,
    )


def grade_expected_woba(
    expected_woba_allowed: float,
) -> int:
    """
    Lower expected wOBA allowed is better.
    """
    return inverse_linear_grade(
        value=expected_woba_allowed,
        elite_value=0.240,
        average_value=0.320,
        poor_value=0.410,
    )


def grade_expected_slugging(
    expected_slugging_allowed: float,
) -> int:
    """
    Lower expected slugging allowed is better.
    """
    return inverse_linear_grade(
        value=expected_slugging_allowed,
        elite_value=0.300,
        average_value=0.430,
        poor_value=0.600,
    )


def grade_fastball_velocity(
    velocity: float,
) -> int:
    """
    Grade primary fastball velocity.
    """
    return linear_grade(
        value=velocity,
        low_value=87,
        average_value=93,
        high_value=99,
    )


def grade_extension(
    extension: float,
) -> int:
    """
    Grade release extension.
    """
    return linear_grade(
        value=extension,
        low_value=5.4,
        average_value=6.2,
        high_value=7.2,
    )

# ARSENAL HELPERS
def get_eligible_pitches(
    arsenal: list[dict[str, Any]],
    minimum_pitches: int = 25,
) -> list[dict[str, Any]]:
    """
    Remove pitches with very small sample sizes.
    """
    return [
        pitch
        for pitch in arsenal
        if int(
            pitch.get(
                "pitch_count",
                0,
            )
        ) >= minimum_pitches
    ]


def get_primary_fastball(
    arsenal: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Return the most-used fastball type.
    """
    fastball_types = {
        "FF",
        "SI",
        "FC",
        "FA",
    }

    fastballs = [
        pitch
        for pitch in arsenal
        if pitch.get("pitch_type") in fastball_types
    ]

    if not fastballs:
        return None

    return max(
        fastballs,
        key=lambda pitch: int(
            pitch.get(
                "pitch_count",
                0,
            )
        ),
    )


def get_best_pitch_grade(
    arsenal: list[dict[str, Any]],
    minimum_pitches: int = 25,
) -> int:
    """
    Return the best individual pitch grade.
    """
    graded_pitches = grade_individual_pitches(
        arsenal=arsenal,
        minimum_pitches=minimum_pitches,
    )

    if not graded_pitches:
        return 50

    return max(
        pitch["overall_pitch_grade"]
        for pitch in graded_pitches
    )

# INDIVIDUAL PITCH GRADES
def grade_single_pitch(
    pitch: dict[str, Any],
) -> dict[str, Any]:
    """
    Grade one pitch using its outcomes and traits.
    """
    whiff_grade = grade_whiff_rate(
        safe_float(
            pitch.get("whiff_rate")
        )
    )

    chase_grade = grade_chase_rate(
        safe_float(
            pitch.get("chase_rate")
        )
    )

    strike_grade = grade_strike_rate(
        safe_float(
            pitch.get("strike_rate")
        )
    )

    contact_grade = grade_hard_hit_rate(
        safe_float(
            pitch.get("hard_hit_rate")
        )
    )

    expected_woba_grade = grade_expected_woba(
        safe_float(
            pitch.get("expected_woba_allowed"),
            default=0.320,
        )
    )

    overall_pitch_grade = weighted_grade(
        [
            (whiff_grade, 0.30),
            (chase_grade, 0.20),
            (strike_grade, 0.15),
            (contact_grade, 0.15),
            (expected_woba_grade, 0.20),
        ]
    )

    return {
        "pitch_type": pitch.get("pitch_type"),
        "pitch_count": int(
            pitch.get(
                "pitch_count",
                0,
            )
        ),
        "usage_percent": safe_float(
            pitch.get("usage_percent")
        ),
        "velocity": safe_float(
            pitch.get("average_velocity")
        ),
        "spin_rate": safe_float(
            pitch.get("average_spin_rate")
        ),
        "whiff_grade": whiff_grade,
        "chase_grade": chase_grade,
        "strike_grade": strike_grade,
        "contact_grade": contact_grade,
        "expected_woba_grade": expected_woba_grade,
        "overall_pitch_grade": overall_pitch_grade,
    }

def grade_individual_pitches(
    arsenal: list[dict[str, Any]],
    minimum_pitches: int = 25,
) -> list[dict[str, Any]]:
    """
    Grade all pitches that meet the sample threshold.
    """
    eligible = get_eligible_pitches(
        arsenal=arsenal,
        minimum_pitches=minimum_pitches,
    )

    graded = [
        grade_single_pitch(pitch)
        for pitch in eligible
    ]

    return sorted(
        graded,
        key=lambda pitch: (
            pitch["overall_pitch_grade"],
            pitch["pitch_count"],
        ),
        reverse=True,
    )

# CATEGORY GRADES
def calculate_stuff_grade(
    summary: dict[str, Any],
    arsenal: list[dict[str, Any]],
) -> int:
    """
    Stuff grade based on bat missing, chase,
    fastball velocity, and best pitch quality.
    """
    whiff_grade = grade_whiff_rate(
        safe_float(
            summary.get("whiff_rate")
        )
    )

    csw_grade = grade_csw_rate(
        safe_float(
            summary.get("csw_rate")
        )
    )

    chase_grade = grade_chase_rate(
        safe_float(
            summary.get("chase_rate")
        )
    )

    fastball = get_primary_fastball(arsenal)

    if fastball:
        velocity_grade = grade_fastball_velocity(
            safe_float(
                fastball.get("average_velocity")
            )
        )
    else:
        velocity_grade = 50

    best_pitch_grade = get_best_pitch_grade(
        arsenal
    )

    return weighted_grade(
        [
            (whiff_grade, 0.25),
            (csw_grade, 0.20),
            (chase_grade, 0.20),
            (velocity_grade, 0.15),
            (best_pitch_grade, 0.20),
        ]
    )

def calculate_command_grade(
    summary: dict[str, Any],
) -> int:
    """
    Command grade based on strikes, zone rate,
    and ability to get called strikes or whiffs.
    """
    strike_grade = grade_strike_rate(
        safe_float(
            summary.get("strike_rate")
        )
    )

    zone_grade = grade_zone_rate(
        safe_float(
            summary.get("zone_rate")
        )
    )

    csw_grade = grade_csw_rate(
        safe_float(
            summary.get("csw_rate")
        )
    )

    return weighted_grade(
        [
            (strike_grade, 0.50),
            (zone_grade, 0.30),
            (csw_grade, 0.20),
        ]
    )

def calculate_bat_missing_grade(
    summary: dict[str, Any],
) -> int:
    """
    Grade overall ability to miss bats.
    """
    whiff_grade = grade_whiff_rate(
        safe_float(
            summary.get("whiff_rate")
        )
    )

    csw_grade = grade_csw_rate(
        safe_float(
            summary.get("csw_rate")
        )
    )

    contact_grade = grade_contact_rate(
        safe_float(
            summary.get("contact_rate")
        )
    )

    chase_grade = grade_chase_rate(
        safe_float(
            summary.get("chase_rate")
        )
    )

    return weighted_grade(
        [
            (whiff_grade, 0.35),
            (csw_grade, 0.25),
            (contact_grade, 0.20),
            (chase_grade, 0.20),
        ]
    )

def calculate_contact_management_grade(
    summary: dict[str, Any],
) -> int:
    """
    Grade contact suppression and expected outcomes.
    """
    hard_hit_grade = grade_hard_hit_rate(
        safe_float(
            summary.get("hard_hit_rate")
        )
    )

    exit_velocity_grade = grade_exit_velocity(
        safe_float(
            summary.get("average_exit_velocity")
        )
    )

    expected_woba_grade = grade_expected_woba(
        safe_float(
            summary.get("expected_woba_allowed"),
            default=0.320,
        )
    )

    expected_slugging_grade = grade_expected_slugging(
        safe_float(
            summary.get("expected_slugging_allowed"),
            default=0.430,
        )
    )

    return weighted_grade(
        [
            (hard_hit_grade, 0.30),
            (exit_velocity_grade, 0.25),
            (expected_woba_grade, 0.30),
            (expected_slugging_grade, 0.15),
        ]
    )

def calculate_arsenal_grade(
    arsenal: list[dict[str, Any]],
) -> int:
    """
    Grade arsenal depth and pitch quality.
    """
    eligible = get_eligible_pitches(arsenal)

    if not eligible:
        return 40

    pitch_grades = grade_individual_pitches(arsenal)

    usable_pitches = [
        pitch
        for pitch in eligible
        if safe_float(
            pitch.get("usage_percent")
        ) >= 5
    ]

    above_average_pitches = [
        pitch
        for pitch in pitch_grades
        if pitch["overall_pitch_grade"] >= 55
    ]

    depth_count = len(usable_pitches)

    if depth_count >= 5:
        depth_grade = 70
    elif depth_count == 4:
        depth_grade = 60
    elif depth_count == 3:
        depth_grade = 55
    elif depth_count == 2:
        depth_grade = 45
    else:
        depth_grade = 35

    if pitch_grades:
        average_pitch_grade = round_to_five(
            sum(
                pitch["overall_pitch_grade"]
                for pitch in pitch_grades
            )
            / len(pitch_grades)
        )
    else:
        average_pitch_grade = 40

    quality_depth_grade = linear_grade(
        value=len(above_average_pitches),
        low_value=0,
        average_value=2,
        high_value=5,
    )

    return weighted_grade(
        [
            (depth_grade, 0.35),
            (average_pitch_grade, 0.40),
            (quality_depth_grade, 0.25),
        ]
    )


def calculate_overall_grade(
    category_grades: dict[str, int],
) -> int:
    """
    Combine the major categories into one grade.
    """
    return weighted_grade(
        [
            (
                category_grades["stuff"],
                0.30,
            ),
            (
                category_grades["command"],
                0.20,
            ),
            (
                category_grades["bat_missing"],
                0.20,
            ),
            (
                category_grades[
                    "contact_management"
                ],
                0.20,
            ),
            (
                category_grades["arsenal"],
                0.10,
            ),
        ]
    )

# GRADE LABELS
def get_grade_label(
    grade: int,
) -> str:
    """
    Convert a numeric scouting grade into a label.
    """
    if grade >= 80:
        return "Elite"

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

    if grade >= 30:
        return "Poor"

    return "Well Below Average"

def add_grade_labels(
    grades: dict[str, int],
) -> dict[str, dict[str, Any]]:
    """
    Add a descriptive label to every grade.
    """
    return {
        grade_name: {
            "grade": grade_value,
            "label": get_grade_label(
                grade_value
            ),
        }
        for grade_name, grade_value in grades.items()
    }

# COMPLETE PITCHER GRADING PROFILE
def build_pitcher_grades(
    summary: dict[str, Any],
    arsenal: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Build the complete scouting-grade profile.
    """
    category_grades = {
        "stuff": calculate_stuff_grade(
            summary,
            arsenal,
        ),
        "command": calculate_command_grade(
            summary
        ),
        "bat_missing": calculate_bat_missing_grade(
            summary
        ),
        "contact_management": (
            calculate_contact_management_grade(
                summary
            )
        ),
        "arsenal": calculate_arsenal_grade(
            arsenal
        ),
    }

    category_grades["overall"] = (
        calculate_overall_grade(
            category_grades
        )
    )

    return {
        "grades": add_grade_labels(
            category_grades
        ),
        "pitch_grades": grade_individual_pitches(
            arsenal
        ),
        "scale": {
            "80": "Elite",
            "70": "Plus-Plus",
            "60": "Plus",
            "55": "Above Average",
            "50": "Average",
            "45": "Fringe Average",
            "40": "Below Average",
            "30": "Poor",
            "20": "Well Below Average",
        },
    }