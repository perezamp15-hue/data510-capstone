"""Deterministic scouting visual and decision-support calculations.

These functions do not train or alter a machine-learning model. They summarize
historical Statcast tracking data for the HTML report.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any
import math
import numpy as np
import pandas as pd

from analytics.pitch_sequence_engine import PITCH_NAMES


def _num(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[col], errors="coerce")


def _flight_time(row: pd.Series) -> float | None:
    """Approximate time from release to the front of home plate."""
    try:
        y0, vy, ay = float(row["release_pos_y"]), float(row["vy0"]), float(row["ay"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (y0, vy, ay)):
        return None
    target_y = 1.417
    c = y0 - target_y
    if abs(ay) < 1e-8:
        t = -c / vy if vy else -1
        return t if 0.25 <= t <= 0.75 else None
    disc = vy * vy - 2 * ay * c
    if disc < 0:
        return None
    roots = [(-vy + math.sqrt(disc)) / ay, (-vy - math.sqrt(disc)) / ay]
    valid = [t for t in roots if 0.25 <= t <= 0.75]
    return min(valid) if valid else None


def movement_and_release_summary(pitches: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Return movement-proxy and release-point averages by pitch type.

    Horizontal movement is acceleration displacement. Induced vertical movement
    removes gravity from the vertical acceleration term. Both are approximate
    inches over the tracked flight and are intended for within-pitcher comparison.
    """
    if pitches.empty:
        return {"movement": [], "release": []}
    data = pitches.copy()
    needed = ["release_pos_x", "release_pos_y", "release_pos_z", "vy0", "ax", "ay", "az"]
    for col in needed:
        data[col] = _num(data, col)
    data["flight_time"] = data.apply(_flight_time, axis=1)
    t = pd.to_numeric(data["flight_time"], errors="coerce")
    data["horizontal_break_inches"] = 0.5 * data["ax"] * (t ** 2) * 12.0
    data["induced_vertical_break_inches"] = 0.5 * (data["az"] + 32.174) * (t ** 2) * 12.0

    movement, release = [], []
    for code, group in data.groupby("pitch_type"):
        code = str(code)
        valid_m = group.dropna(subset=["horizontal_break_inches", "induced_vertical_break_inches"])
        valid_r = group.dropna(subset=["release_pos_x", "release_pos_z"])
        if len(valid_m) >= 10:
            movement.append({
                "pitch_type": code, "pitch_name": PITCH_NAMES.get(code, code), "sample": len(valid_m),
                "horizontal_break": round(float(valid_m["horizontal_break_inches"].mean()), 1),
                "vertical_break": round(float(valid_m["induced_vertical_break_inches"].mean()), 1),
            })
        if len(valid_r) >= 10:
            release.append({
                "pitch_type": code, "pitch_name": PITCH_NAMES.get(code, code), "sample": len(valid_r),
                "release_x": round(float(valid_r["release_pos_x"].mean()), 2),
                "release_z": round(float(valid_r["release_pos_z"].mean()), 2),
                "release_x_sd": round(float(valid_r["release_pos_x"].std(ddof=0)), 3),
                "release_z_sd": round(float(valid_r["release_pos_z"].std(ddof=0)), 3),
            })
    return {
        "movement": sorted(movement, key=lambda x: x["sample"], reverse=True),
        "release": sorted(release, key=lambda x: x["sample"], reverse=True),
    }


def tunneling_pairs(pitches: pd.DataFrame, maximum: int = 8) -> list[dict[str, Any]]:
    """Rank pitch pairs with similar release points and useful late separation.

    This is a transparent compatibility proxy, not full trajectory reconstruction.
    """
    visual = movement_and_release_summary(pitches)
    mov = {x["pitch_type"]: x for x in visual["movement"]}
    rel = {x["pitch_type"]: x for x in visual["release"]}
    velo = {}
    for code, group in pitches.groupby("pitch_type") if not pitches.empty else []:
        v = _num(group, "release_velocity").dropna()
        if len(v) >= 10:
            velo[str(code)] = float(v.mean())
    common = sorted(set(mov) & set(rel) & set(velo))
    rows = []
    for a, b in combinations(common, 2):
        release_distance = math.hypot(rel[a]["release_x"] - rel[b]["release_x"], rel[a]["release_z"] - rel[b]["release_z"])
        movement_sep = math.hypot(mov[a]["horizontal_break"] - mov[b]["horizontal_break"], mov[a]["vertical_break"] - mov[b]["vertical_break"])
        velo_sep = abs(velo[a] - velo[b])
        release_score = max(0.0, 100.0 - release_distance * 250.0)
        separation_score = min(100.0, movement_sep * 4.0 + velo_sep * 3.0)
        score = 0.65 * release_score + 0.35 * separation_score
        rows.append({
            "pitch_a": a, "pitch_a_name": PITCH_NAMES.get(a, a),
            "pitch_b": b, "pitch_b_name": PITCH_NAMES.get(b, b),
            "score": round(score, 1), "release_distance_ft": round(release_distance, 3),
            "velocity_separation_mph": round(velo_sep, 1), "movement_separation_in": round(movement_sep, 1),
            "explanation": f"Release points are {release_distance:.2f} ft apart with {velo_sep:.1f} mph velocity and {movement_sep:.1f} in movement separation.",
        })
    return sorted(rows, key=lambda x: x["score"], reverse=True)[:maximum]


def recommendation_confidence(option: dict[str, Any] | None, batter_pitch_sample: int, pitcher_pitch_count: int) -> dict[str, Any]:
    if not option:
        return {"score": 0, "label": "Low", "reasons": ["No reliable pitch option was available."]}
    quality = max(0.0, min(100.0, float(option.get("score") or 0.0)))
    batter_reliability = min(max(batter_pitch_sample, 0) / 100.0, 1.0)
    pitcher_reliability = min(max(pitcher_pitch_count, 0) / 100.0, 1.0)
    confidence = round(0.55 * quality + 25 * batter_reliability + 20 * pitcher_reliability)
    label = "High" if confidence >= 75 else "Medium" if confidence >= 55 else "Low"
    reasons = [
        f"Matchup score: {quality:.1f}/100.",
        f"Batter sample against this pitch: {batter_pitch_sample} pitches.",
        f"Pitcher arsenal sample: {pitcher_pitch_count} pitches.",
    ]
    return {"score": int(confidence), "label": label, "reasons": reasons}


def build_decision_tree(options: list[dict[str, Any]]) -> dict[str, Any]:
    if not options:
        return {}
    first = options[0]
    ahead = max(options, key=lambda x: (float(x.get("expected_whiff_rate") or 0), float(x.get("score") or 0)))
    behind = max(options, key=lambda x: (float(x.get("score") or 0) + (8 if x.get("pitch_type") in {"FF", "SI", "FC"} else 0)))
    two = ahead
    return {
        "start": {"label": "0-0", "pitch": first.get("pitch_type"), "target": first.get("zone")},
        "called_strike_or_foul": {"label": "Ahead", "pitch": ahead.get("pitch_type"), "target": ahead.get("zone")},
        "ball": {"label": "Behind", "pitch": behind.get("pitch_type"), "target": behind.get("zone")},
        "two_strikes": {"label": "Put-away", "pitch": two.get("pitch_type"), "target": two.get("zone")},
    }


def executive_summary(lineup: list[dict[str, Any]], arsenal: list[dict[str, Any]], tunnels: list[dict[str, Any]]) -> dict[str, Any]:
    if not lineup:
        return {}
    risk_avg = float(np.mean([float(x.get("risk_score") or 0) for x in lineup]))
    grade = "A" if risk_avg < 42 else "B" if risk_avg < 55 else "C" if risk_avg < 68 else "D"
    highest = max(lineup, key=lambda x: float(x.get("risk_score") or 0))
    safest = min(lineup, key=lambda x: float(x.get("risk_score") or 0))
    primary_counts: dict[str, int] = {}
    for h in lineup:
        p = str(h.get("primary_pitch") or "")
        primary_counts[p] = primary_counts.get(p, 0) + 1
    best_pitch = max(primary_counts, key=primary_counts.get) if primary_counts else ""
    worst = max(arsenal, key=lambda x: float(x.get("xwoba_allowed") or 0.0)) if arsenal else {}
    return {
        "matchup_grade": grade,
        "highest_risk_hitter": highest.get("batter_name", "—"),
        "lowest_risk_hitter": safest.get("batter_name", "—"),
        "most_recommended_pitch": best_pitch,
        "avoid_pitch": worst.get("pitch_type", "—"),
        "best_tunnel": f"{tunnels[0]['pitch_a']} + {tunnels[0]['pitch_b']}" if tunnels else "Not enough tracking data",
    }
