from __future__ import annotations
from typing import Any
import pandas as pd
from analytics.pitcher_grade import build_pitcher_grades
from analytics.pitcher_metrics import (
    calculate_pitch_arsenal,
    calculate_pitcher_summary,
    calculate_velocity_distribution,
)

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Convert a value to float safely.
    """
    if value is None or pd.isna(value):
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def get_pitcher_identity(
    pitches: pd.DataFrame,
) -> dict[str, Any]:
    """
    Extract pitcher metadata from the pitch-level DataFrame.
    """
    if pitches.empty:
        return {
            "pitcher_id": None,
            "pitcher_name": None,
            "throws": None,
            "season": None,
        }

    first_row = pitches.iloc[0]

    return {
        "pitcher_id": (
            int(first_row["pitcher_id"])
            if pd.notna(first_row.get("pitcher_id"))
            else None
        ),
        "pitcher_name": first_row.get("pitcher_name"),
        "throws": first_row.get("pitcher_throws"),
        "season": (
            int(first_row["season"])
            if pd.notna(first_row.get("season"))
            else None
        ),
    }

def get_primary_pitch(
    arsenal: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Return the most frequently used pitch.
    """
    if not arsenal:
        return None

    return max(
        arsenal,
        key=lambda pitch: pitch.get("pitch_count", 0),
    )

def get_best_whiff_pitch(
    arsenal: list[dict[str, Any]],
    minimum_pitches: int = 25,
) -> dict[str, Any] | None:
    """
    Return the pitch with the highest whiff rate,
    requiring a minimum sample size.
    """
    eligible = [
        pitch
        for pitch in arsenal
        if pitch.get("pitch_count", 0) >= minimum_pitches
    ]

    if not eligible:
        return None

    return max(
        eligible,
        key=lambda pitch: safe_float(
            pitch.get("whiff_rate")
        ),
    )

def get_best_chase_pitch(
    arsenal: list[dict[str, Any]],
    minimum_pitches: int = 25,
) -> dict[str, Any] | None:
    """
    Return the pitch with the highest chase rate.
    """
    eligible = [
        pitch
        for pitch in arsenal
        if pitch.get("pitch_count", 0) >= minimum_pitches
    ]

    if not eligible:
        return None

    return max(
        eligible,
        key=lambda pitch: safe_float(
            pitch.get("chase_rate")
        ),
    )

def get_best_strike_pitch(
    arsenal: list[dict[str, Any]],
    minimum_pitches: int = 25,
) -> dict[str, Any] | None:
    """
    Return the pitch with the highest strike rate.
    """
    eligible = [
        pitch
        for pitch in arsenal
        if pitch.get("pitch_count", 0) >= minimum_pitches
    ]

    if not eligible:
        return None

    return max(
        eligible,
        key=lambda pitch: safe_float(
            pitch.get("strike_rate")
        ),
    )

# PITCHER CLASSIFICATION
def classify_velocity(
    arsenal: list[dict[str, Any]],
) -> str:
    """
    Classify fastball velocity.
    """
    fastball_types = {
        "FF",
        "SI",
        "FC",
    }

    fastballs = [
        pitch
        for pitch in arsenal
        if pitch.get("pitch_type") in fastball_types
        and pitch.get("average_velocity") is not None
    ]

    if not fastballs:
        return "unknown velocity profile"

    primary_fastball = max(
        fastballs,
        key=lambda pitch: pitch.get("pitch_count", 0),
    )

    velocity = safe_float(
        primary_fastball.get("average_velocity")
    )

    if velocity >= 97:
        return "elite velocity"

    if velocity >= 95:
        return "plus velocity"

    if velocity >= 93:
        return "average velocity"

    if velocity >= 90:
        return "below-average velocity"

    return "low velocity"

def classify_command(
    summary: dict[str, Any],
) -> str:
    """
    Classify strike-throwing and zone control.
    """
    strike_rate = safe_float(summary.get("strike_rate"))
    zone_rate = safe_float(summary.get("zone_rate"))

    if strike_rate >= 68 and zone_rate >= 45:
        return "aggressive strike thrower"

    if strike_rate >= 65:
        return "solid strike thrower"

    if strike_rate >= 62:
        return "average command profile"

    return "inconsistent strike thrower"

def classify_bat_missing(
    summary: dict[str, Any],
) -> str:
    """
    Classify bat-missing ability.
    """
    whiff_rate = safe_float(summary.get("whiff_rate"))
    csw_rate = safe_float(summary.get("csw_rate"))

    if whiff_rate >= 32 or csw_rate >= 31:
        return "elite bat-missing ability"

    if whiff_rate >= 27 or csw_rate >= 29:
        return "above-average bat-missing ability"

    if whiff_rate >= 22 or csw_rate >= 26:
        return "average bat-missing ability"

    return "contact-oriented profile"

def classify_chase_profile(
    summary: dict[str, Any],
) -> str:
    """
    Classify the pitcher's ability to induce swings
    outside the strike zone.
    """
    chase_rate = safe_float(summary.get("chase_rate"))

    if chase_rate >= 38:
        return "elite chase generation"

    if chase_rate >= 33:
        return "strong chase generation"

    if chase_rate >= 28:
        return "average chase generation"

    return "limited chase generation"

def classify_contact_quality(
    summary: dict[str, Any],
) -> str:
    """
    Classify batted-ball contact quality allowed.
    """
    hard_hit_rate = safe_float(
        summary.get("hard_hit_rate")
    )

    average_exit_velocity = safe_float(
        summary.get("average_exit_velocity")
    )

    if (
        hard_hit_rate <= 25
        and average_exit_velocity <= 84
    ):
        return "excellent contact suppression"

    if (
        hard_hit_rate <= 32
        and average_exit_velocity <= 87
    ):
        return "strong contact suppression"

    if hard_hit_rate <= 38:
        return "average contact management"

    return "vulnerable to hard contact"

def classify_arsenal_shape(
    arsenal: list[dict[str, Any]],
) -> str:
    """
    Classify how broad the pitcher's usable arsenal is.
    """
    usable_pitches = [
        pitch
        for pitch in arsenal
        if safe_float(
            pitch.get("usage_percent")
        ) >= 5
    ]

    pitch_count = len(usable_pitches)

    if pitch_count >= 5:
        return "deep multi-pitch arsenal"

    if pitch_count == 4:
        return "four-pitch arsenal"

    if pitch_count == 3:
        return "three-pitch arsenal"

    if pitch_count == 2:
        return "two-pitch dominant arsenal"

    return "single-pitch dominant profile"

def classify_pitcher_type(
    summary: dict[str, Any],
    arsenal: list[dict[str, Any]],
) -> str:
    """
    Produce the main pitcher archetype.
    """
    velocity = classify_velocity(arsenal)
    bat_missing = classify_bat_missing(summary)
    chase = classify_chase_profile(summary)
    command = classify_command(summary)
    arsenal_shape = classify_arsenal_shape(arsenal)

    if (
        velocity in {"elite velocity", "plus velocity"}
        and bat_missing
        in {
            "elite bat-missing ability",
            "above-average bat-missing ability",
        }
    ):
        return (
            "Power pitcher with premium velocity "
            "and swing-and-miss ability"
        )

    if (
        chase
        in {
            "elite chase generation",
            "strong chase generation",
        }
        and arsenal_shape
        in {
            "deep multi-pitch arsenal",
            "four-pitch arsenal",
        }
    ):
        return (
            "Deep-arsenal pitcher who wins through "
            "chase and pitch variety"
        )

    if command == "aggressive strike thrower":
        return (
            "Command-oriented pitcher who attacks "
            "the strike zone"
        )

    if bat_missing == "contact-oriented profile":
        return (
            "Contact-management pitcher who relies "
            "on sequencing and weak contact"
        )

    return (
        "Balanced pitcher with a mix of command, "
        "chase, and contact management"
    )

# STRENGTHS AND CONCERNS
def build_strengths(
    summary: dict[str, Any],
    arsenal: list[dict[str, Any]],
) -> list[str]:
    """
    Generate strengths for the scouting report.
    """
    strengths: list[str] = []

    if safe_float(summary.get("chase_rate")) >= 35:
        strengths.append(
            "Generates frequent swings outside the strike zone."
        )

    if safe_float(summary.get("whiff_rate")) >= 25:
        strengths.append(
            "Produces a strong overall swing-and-miss rate."
        )

    if safe_float(summary.get("strike_rate")) >= 65:
        strengths.append(
            "Throws strikes at a strong overall rate."
        )

    if safe_float(summary.get("hard_hit_rate")) <= 30:
        strengths.append(
            "Limits hard contact effectively."
        )

    if safe_float(
        summary.get("average_exit_velocity")
    ) <= 85:
        strengths.append(
            "Suppresses average exit velocity."
        )

    best_whiff = get_best_whiff_pitch(arsenal)

    if (
        best_whiff
        and safe_float(
            best_whiff.get("whiff_rate")
        ) >= 30
    ):
        strengths.append(
            f"{best_whiff['pitch_type']} is the primary "
            f"swing-and-miss weapon with a "
            f"{best_whiff['whiff_rate']:.1f}% whiff rate."
        )

    best_chase = get_best_chase_pitch(arsenal)

    if (
        best_chase
        and safe_float(
            best_chase.get("chase_rate")
        ) >= 40
    ):
        strengths.append(
            f"{best_chase['pitch_type']} generates "
            f"excellent chase at "
            f"{best_chase['chase_rate']:.1f}%."
        )

    return strengths


def build_concerns(
    summary: dict[str, Any],
    arsenal: list[dict[str, Any]],
) -> list[str]:
    """
    Generate possible concerns for the scouting report.
    """
    concerns: list[str] = []

    if safe_float(summary.get("zone_rate")) < 40:
        concerns.append(
            "Works outside the strike zone frequently."
        )

    if safe_float(summary.get("strike_rate")) < 62:
        concerns.append(
            "Overall strike throwing may be inconsistent."
        )

    if safe_float(summary.get("hard_hit_rate")) >= 38:
        concerns.append(
            "Allows a high rate of hard contact."
        )

    if safe_float(summary.get("contact_rate")) >= 80:
        concerns.append(
            "Does not miss many bats when hitters swing."
        )

    for pitch in arsenal:
        pitch_count = int(
            pitch.get("pitch_count", 0)
        )

        if pitch_count < 25:
            continue

        whiff_rate = safe_float(
            pitch.get("whiff_rate")
        )

        if whiff_rate < 10:
            concerns.append(
                f"{pitch['pitch_type']} produces limited "
                f"swing-and-miss at "
                f"{whiff_rate:.1f}%."
            )

    return concerns

# SCOUTING SUMMARY
def build_scouting_summary(
    identity: dict[str, Any],
    summary: dict[str, Any],
    arsenal: list[dict[str, Any]],
) -> str:
    """
    Build a short human-readable scouting summary.
    """
    pitcher_name = (
        identity.get("pitcher_name")
        or "This pitcher"
    )

    primary_pitch = get_primary_pitch(arsenal)
    best_whiff = get_best_whiff_pitch(arsenal)
    pitcher_type = classify_pitcher_type(
        summary,
        arsenal,
    )

    sentences = [
        f"{pitcher_name} profiles as a "
        f"{pitcher_type.lower()}."
    ]

    if primary_pitch:
        sentences.append(
            f"The primary offering is the "
            f"{primary_pitch['pitch_type']}, used "
            f"{primary_pitch['usage_percent']:.1f}% of the time "
            f"at an average velocity of "
            f"{safe_float(primary_pitch.get('average_velocity')):.1f} mph."
        )

    if best_whiff:
        sentences.append(
            f"The strongest bat-missing pitch is the "
            f"{best_whiff['pitch_type']}, which generated a "
            f"{best_whiff['whiff_rate']:.1f}% whiff rate."
        )

    sentences.append(
        f"Overall, the pitcher recorded a "
        f"{safe_float(summary.get('strike_rate')):.1f}% strike rate, "
        f"{safe_float(summary.get('whiff_rate')):.1f}% whiff rate, "
        f"and {safe_float(summary.get('chase_rate')):.1f}% chase rate."
    )

    return " ".join(sentences)

# COMPLETE PROFILE
def build_pitcher_profile(
    pitches: pd.DataFrame,
) -> dict[str, Any]:
    """
    Build the complete pitcher scouting profile.
    """
    if pitches.empty:
        return {
            "identity": {},
            "classification": None,
            "summary": {},
            "arsenal": [],
            "velocity_distribution": [],
            "highlights": {},
            "strengths": [],
            "concerns": [],
            "scouting_summary": None,
        }

    identity = get_pitcher_identity(pitches)
    summary = calculate_pitcher_summary(pitches)
    arsenal = calculate_pitch_arsenal(pitches)
    grades = build_pitcher_grades(
    summary=summary,
    arsenal=arsenal,
    )
    velocity_distribution = (
        calculate_velocity_distribution(pitches)
    )

    primary_pitch = get_primary_pitch(arsenal)
    best_whiff_pitch = get_best_whiff_pitch(arsenal)
    best_chase_pitch = get_best_chase_pitch(arsenal)
    best_strike_pitch = get_best_strike_pitch(arsenal)

    return {
    "identity": identity,
    "classification": {
        "pitcher_type": classify_pitcher_type(
            summary,
            arsenal,
        ),
        "velocity_profile": classify_velocity(
            arsenal
        ),
        "command_profile": classify_command(
            summary
        ),
        "bat_missing_profile": classify_bat_missing(
            summary
        ),
        "chase_profile": classify_chase_profile(
            summary
        ),
        "contact_profile": classify_contact_quality(
            summary
        ),
        "arsenal_shape": classify_arsenal_shape(
            arsenal
        ),
    },
    "summary": summary,
    "grades": grades,
    "arsenal": arsenal,
    "velocity_distribution": velocity_distribution,
    "highlights": {
        "primary_pitch": primary_pitch,
        "best_whiff_pitch": best_whiff_pitch,
        "best_chase_pitch": best_chase_pitch,
        "best_strike_pitch": best_strike_pitch,
    },
    "strengths": build_strengths(
        summary,
        arsenal,
    ),
    "concerns": build_concerns(
        summary,
        arsenal,
    ),
    "scouting_summary": build_scouting_summary(
        identity,
        summary,
        arsenal,
    ),
}