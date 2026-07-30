from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

SWING = {
    "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
    "foul_bunt", "hit_into_play",
}
WHIFF = {"swinging_strike", "swinging_strike_blocked"}
CALLED_STRIKE = {"called_strike"}
CONTACT = {"foul", "foul_tip", "foul_bunt", "hit_into_play"}
WALK_EVENTS = {"walk", "intent_walk"}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
HIT_EVENTS = {"single", "double", "triple", "home_run"}

PITCH_NAMES = {
    "FF": "4-Seam", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
    "ST": "Sweeper", "CU": "Curveball", "KC": "Knuckle Curve",
    "CH": "Changeup", "FS": "Splitter", "FO": "Forkball",
    "KN": "Knuckleball", "EP": "Eephus",
}

FASTBALLS = {"FF", "SI", "FC"}
BREAKING = {"SL", "ST", "CU", "KC"}
OFFSPEED = {"CH", "FS", "FO"}


@dataclass(frozen=True)
class PitchOption:
    pitch_type: str
    zone: str
    score: float
    rationale: str
    expected_whiff_rate: float
    expected_xwoba: float | None


def _text(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].fillna("").astype(str).str.strip().str.lower()


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _pct(numerator: float, denominator: float) -> float:
    return round(float(numerator) / float(denominator) * 100.0, 1) if denominator else 0.0


def add_flags(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    descriptions = _text(data, "pitch_description")
    events = _text(data, "events")
    data["is_swing"] = descriptions.isin(SWING)
    data["is_whiff"] = descriptions.isin(WHIFF)
    data["is_called_strike"] = descriptions.isin(CALLED_STRIKE)
    data["is_contact"] = descriptions.isin(CONTACT)
    data["is_in_play"] = descriptions.eq("hit_into_play")
    data["is_walk_event"] = events.isin(WALK_EVENTS)
    data["is_strikeout_event"] = events.isin(STRIKEOUT_EVENTS)
    data["is_hit_event"] = events.isin(HIT_EVENTS)

    px = _numeric(data, "plate_x")
    pz = _numeric(data, "plate_z")
    top = _numeric(data, "sz_top")
    bottom = _numeric(data, "sz_bottom")
    valid = px.notna() & pz.notna() & top.notna() & bottom.notna() & top.gt(bottom)
    data["is_in_zone"] = (
        valid
        & px.between(-17 / 24, 17 / 24, inclusive="both")
        & pz.between(bottom, top, inclusive="both")
    )
    data["is_chase"] = data["is_swing"] & valid & ~data["is_in_zone"]
    data["location_bucket"] = location_bucket(px, pz, top, bottom)
    return data


def location_bucket(
    plate_x: pd.Series,
    plate_z: pd.Series,
    sz_top: pd.Series,
    sz_bottom: pd.Series,
) -> pd.Series:
    midpoint = (sz_top + sz_bottom) / 2
    result = pd.Series("unknown", index=plate_x.index, dtype="object")
    result.loc[plate_z > sz_top] = "high"
    result.loc[plate_z < sz_bottom] = "below"
    in_vertical = plate_z.between(sz_bottom, sz_top, inclusive="both")
    result.loc[in_vertical & (plate_x < -17 / 24)] = "outside-left"
    result.loc[in_vertical & (plate_x > 17 / 24)] = "outside-right"
    result.loc[in_vertical & plate_x.between(-17 / 24, 17 / 24)] = "middle"
    result.loc[in_vertical & plate_x.between(-17 / 24, -0.20)] = "inside-left"
    result.loc[in_vertical & plate_x.between(0.20, 17 / 24)] = "inside-right"
    result.loc[in_vertical & plate_x.between(-0.20, 0.20) & (plate_z >= midpoint)] = "upper-middle"
    result.loc[in_vertical & plate_x.between(-0.20, 0.20) & (plate_z < midpoint)] = "lower-middle"
    return result


def terminal_plate_appearances(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    sort_columns = [
        column for column in [
            "game_date", "game_pk", "at_bat_number", "plate_appearance_number", "pitch_number"
        ] if column in frame.columns
    ]
    ordered = frame.sort_values(sort_columns) if sort_columns else frame.copy()
    keys = [column for column in ["game_pk", "at_bat_number"] if column in ordered.columns]
    if len(keys) < 2:
        keys = [column for column in ["game_pk", "plate_appearance_number"] if column in ordered.columns]
    if not keys:
        return ordered
    return ordered.groupby(keys, dropna=False).tail(1).copy()


def summarize_pitcher_arsenal(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    data = add_flags(pitches)
    total = len(data)
    rows: list[dict[str, Any]] = []
    for pitch_type, group in data.loc[data["pitch_type"].notna()].groupby("pitch_type"):
        swings = int(group["is_swing"].sum())
        batted = group.loc[group["is_in_play"] & _numeric(group, "exit_velocity").notna()]
        rows.append({
            "pitch_type": str(pitch_type),
            "pitch_name": PITCH_NAMES.get(str(pitch_type), str(pitch_type)),
            "pitch_count": len(group),
            "usage_rate": _pct(len(group), total),
            "average_velocity": round(float(_numeric(group, "release_velocity").mean()), 1)
                if _numeric(group, "release_velocity").notna().any() else None,
            "strike_rate": _pct(int((group["is_called_strike"] | group["is_whiff"] | group["is_contact"]).sum()), len(group)),
            "whiff_rate": _pct(int(group["is_whiff"].sum()), swings),
            "chase_rate": _pct(int(group["is_chase"].sum()), int((~group["is_in_zone"]).sum())),
            "zone_rate": _pct(int(group["is_in_zone"].sum()), len(group)),
            "xwoba_allowed": round(float(_numeric(group, "expected_woba").mean()), 3)
                if _numeric(group, "expected_woba").notna().any() else None,
            "average_exit_velocity": round(float(_numeric(batted, "exit_velocity").mean()), 1)
                if not batted.empty and _numeric(batted, "exit_velocity").notna().any() else None,
        })
    return sorted(rows, key=lambda row: row["pitch_count"], reverse=True)


def summarize_batter(pitches: pd.DataFrame) -> dict[str, Any]:
    data = add_flags(pitches)
    terminal = terminal_plate_appearances(data)
    events = _text(terminal, "events")
    pa = len(terminal)
    swings = int(data["is_swing"].sum())
    batted = data.loc[data["is_in_play"] & _numeric(data, "exit_velocity").notna()]
    hits = int(events.isin(HIT_EVENTS).sum())
    walks = int(events.isin(WALK_EVENTS).sum())
    strikeouts = int(events.isin(STRIKEOUT_EVENTS).sum())
    return {
        "plate_appearances": pa,
        "hits": hits,
        "walks": walks,
        "strikeouts": strikeouts,
        "hit_rate": _pct(hits, pa),
        "walk_rate": _pct(walks, pa),
        "strikeout_rate": _pct(strikeouts, pa),
        "swing_rate": _pct(swings, len(data)),
        "whiff_rate": _pct(int(data["is_whiff"].sum()), swings),
        "chase_rate": _pct(int(data["is_chase"].sum()), int((~data["is_in_zone"]).sum())),
        "xwoba": round(float(_numeric(data, "expected_woba").mean()), 3)
            if _numeric(data, "expected_woba").notna().any() else None,
        "average_exit_velocity": round(float(_numeric(batted, "exit_velocity").mean()), 1)
            if not batted.empty and _numeric(batted, "exit_velocity").notna().any() else None,
        "hard_hit_rate": _pct(int((_numeric(batted, "exit_velocity") >= 95).sum()), len(batted)),
    }


def summarize_batter_by_pitch(pitches: pd.DataFrame) -> dict[str, dict[str, Any]]:
    data = add_flags(pitches)
    output: dict[str, dict[str, Any]] = {}
    for pitch_type, group in data.loc[data["pitch_type"].notna()].groupby("pitch_type"):
        swings = int(group["is_swing"].sum())
        terminal = terminal_plate_appearances(group)
        events = _text(terminal, "events")
        batted = group.loc[group["is_in_play"] & _numeric(group, "exit_velocity").notna()]
        output[str(pitch_type)] = {
            "pitches": len(group),
            "whiff_rate": _pct(int(group["is_whiff"].sum()), swings),
            "chase_rate": _pct(int(group["is_chase"].sum()), int((~group["is_in_zone"]).sum())),
            "hit_rate": _pct(int(events.isin(HIT_EVENTS).sum()), len(terminal)),
            "xwoba": round(float(_numeric(group, "expected_woba").mean()), 3)
                if _numeric(group, "expected_woba").notna().any() else None,
            "average_exit_velocity": round(float(_numeric(batted, "exit_velocity").mean()), 1)
                if not batted.empty and _numeric(batted, "exit_velocity").notna().any() else None,
        }
    return output


def summarize_direct_matchup(pitches: pd.DataFrame) -> dict[str, Any]:
    if pitches.empty:
        return {"plate_appearances": 0, "hits": 0, "walks": 0, "strikeouts": 0, "xwoba": None}
    summary = summarize_batter(pitches)
    return {
        "plate_appearances": summary["plate_appearances"],
        "hits": summary["hits"],
        "walks": summary["walks"],
        "strikeouts": summary["strikeouts"],
        "xwoba": summary["xwoba"],
    }


def _pitch_family(pitch_type: str) -> str:
    if pitch_type in FASTBALLS:
        return "fastball"
    if pitch_type in BREAKING:
        return "breaking"
    if pitch_type in OFFSPEED:
        return "offspeed"
    return "other"


def _recommended_zone(pitch_type: str, batter_side: str) -> str:
    side = (batter_side or "").upper()
    if pitch_type == "FF":
        return "upper third"
    if pitch_type in {"SL", "ST", "CU", "KC"}:
        return "down and away" if side == "R" else "down and in"
    if pitch_type in {"CH", "FS", "FO"}:
        return "below the zone"
    if pitch_type == "SI":
        return "arm-side edge"
    if pitch_type == "FC":
        return "glove-side edge"
    return "zone edge"


def score_pitch_options(
    arsenal: Iterable[dict[str, Any]],
    batter_by_pitch: dict[str, dict[str, Any]],
    batter_side: str,
) -> list[PitchOption]:
    options: list[PitchOption] = []
    for pitch in arsenal:
        pitch_type = str(pitch["pitch_type"])
        batter_metrics = batter_by_pitch.get(pitch_type, {})
        pitcher_whiff = float(pitch.get("whiff_rate") or 0.0)
        pitcher_chase = float(pitch.get("chase_rate") or 0.0)
        pitcher_xwoba = pitch.get("xwoba_allowed")
        batter_whiff = float(batter_metrics.get("whiff_rate") or 0.0)
        batter_chase = float(batter_metrics.get("chase_rate") or 0.0)
        batter_xwoba = batter_metrics.get("xwoba")
        sample = int(batter_metrics.get("pitches") or 0)
        sample_weight = min(sample / 100.0, 1.0)

        xwoba_component = 50.0
        xwoba_values = [value for value in [pitcher_xwoba, batter_xwoba] if value is not None]
        if xwoba_values:
            xwoba_component = max(0.0, min(100.0, (0.450 - float(np.mean(xwoba_values))) / 0.300 * 100.0))

        whiff_component = (pitcher_whiff * (1 - sample_weight) + batter_whiff * sample_weight)
        chase_component = (pitcher_chase * (1 - sample_weight) + batter_chase * sample_weight)
        command_component = float(pitch.get("strike_rate") or 0.0)
        raw_score = 0.38 * whiff_component + 0.22 * chase_component + 0.25 * xwoba_component + 0.15 * command_component
        pitcher_pitch_count = int(pitch.get("pitch_count") or 0)
        pitcher_usage = float(pitch.get("usage_rate") or 0.0)
        reliability = min(pitcher_pitch_count / 100.0, 1.0)
        # Regress tiny arsenal samples toward a neutral score. A rarely used pitch
        # may remain a surprise option, but it should not dominate the primary plan.
        score = 50.0 + (raw_score - 50.0) * reliability
        if pitcher_usage < 3.0 and pitcher_pitch_count < 50:
            score -= 12.0

        rationale_parts = []
        if whiff_component >= 30:
            rationale_parts.append("strong bat-missing profile")
        if chase_component >= 30:
            rationale_parts.append("can expand the zone")
        if xwoba_component >= 60:
            rationale_parts.append("limits expected damage")
        if not rationale_parts:
            rationale_parts.append("best available arsenal fit")

        options.append(PitchOption(
            pitch_type=pitch_type,
            zone=_recommended_zone(pitch_type, batter_side),
            score=round(score, 1),
            rationale=", ".join(rationale_parts),
            expected_whiff_rate=round(whiff_component, 1),
            expected_xwoba=round(float(np.mean(xwoba_values)), 3) if xwoba_values else None,
        ))
    return sorted(options, key=lambda option: option.score, reverse=True)


def build_sequences(options: list[PitchOption], maximum: int = 3) -> list[dict[str, Any]]:
    if not options:
        return []
    selected = options[: min(5, len(options))]
    sequences: list[dict[str, Any]] = []
    candidates: list[tuple[float, list[PitchOption]]] = []
    for first in selected:
        for second in selected:
            if second.pitch_type == first.pitch_type and len(selected) > 1:
                continue
            for third in selected:
                if third.pitch_type == second.pitch_type and len(selected) > 1:
                    continue
                family_change_bonus = 6.0 if _pitch_family(first.pitch_type) != _pitch_family(second.pitch_type) else 0.0
                finish_bonus = 5.0 if third.expected_whiff_rate >= 30 else 0.0
                score = 0.30 * first.score + 0.30 * second.score + 0.40 * third.score + family_change_bonus + finish_bonus
                candidates.append((score, [first, second, third]))
    candidates.sort(key=lambda item: item[0], reverse=True)
    seen: set[tuple[str, ...]] = set()
    for score, sequence in candidates:
        key = tuple(option.pitch_type for option in sequence)
        if key in seen:
            continue
        seen.add(key)
        sequences.append({
            "sequence_score": round(score, 1),
            "pitches": [
                {
                    "number": index + 1,
                    "pitch_type": option.pitch_type,
                    "pitch_name": PITCH_NAMES.get(option.pitch_type, option.pitch_type),
                    "target_zone": option.zone,
                    "rationale": option.rationale,
                }
                for index, option in enumerate(sequence)
            ],
        })
        if len(sequences) >= maximum:
            break
    return sequences
