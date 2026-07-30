"""Scouting summaries for the opposing pitcher."""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any
import pandas as pd
from analytics.pitch_sequence_engine import add_flags, summarize_pitcher_arsenal, PITCH_NAMES
from reports.pitch_heatmaps import build_location_heatmaps


def _strengths_and_weaknesses(arsenal: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    strengths, weaknesses = [], []
    for p in arsenal:
        name = p.get("pitch_name") or p.get("pitch_type")
        whiff, chase = float(p.get("whiff_rate") or 0), float(p.get("chase_rate") or 0)
        strike, xwoba = float(p.get("strike_rate") or 0), p.get("xwoba_allowed")
        if whiff >= 30:
            strengths.append(f"{name}: strong bat-missing pitch ({whiff:.1f}% whiff rate).")
        elif chase >= 30:
            strengths.append(f"{name}: expands the zone well ({chase:.1f}% chase rate).")
        if xwoba is not None and float(xwoba) >= .360:
            weaknesses.append(f"{name}: allows elevated expected damage ({float(xwoba):.3f} xwOBA).")
        if strike and strike < 58:
            weaknesses.append(f"{name}: below-average strike frequency ({strike:.1f}%).")
    if not strengths and arsenal:
        best = min(arsenal, key=lambda p: float(p.get("xwoba_allowed") or .500))
        strengths.append(f"Best damage-prevention pitch: {best.get('pitch_name', best.get('pitch_type'))}.")
    if not weaknesses and arsenal:
        worst = max(arsenal, key=lambda p: float(p.get("xwoba_allowed") or .000))
        weaknesses.append(f"Most attackable pitch by expected damage: {worst.get('pitch_name', worst.get('pitch_type'))}.")
    return strengths[:6], weaknesses[:6]


def _usage_by_count(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    if pitches.empty:
        return []
    data = pitches.copy()
    data["count"] = data["ball_count"].fillna(0).astype(int).astype(str) + "-" + data["strike_count"].fillna(0).astype(int).astype(str)
    rows = []
    for count, group in data.groupby("count"):
        values = group["pitch_type"].value_counts(normalize=True).head(4)
        rows.append({"count": count, "sample": len(group), "usage": {str(k): round(float(v)*100, 1) for k,v in values.items()}})
    order = {f"{b}-{s}": b*3+s for b in range(4) for s in range(3)}
    return sorted(rows, key=lambda r: order.get(r["count"], 99))


def _transitions(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    if pitches.empty:
        return []
    sort_cols = [c for c in ["game_date", "game_pk", "at_bat_number", "pitch_number"] if c in pitches]
    data = pitches.sort_values(sort_cols).copy() if sort_cols else pitches.copy()
    keys = [c for c in ["game_pk", "at_bat_number"] if c in data]
    if len(keys) < 2:
        return []
    data["previous_pitch"] = data.groupby(keys)["pitch_type"].shift(1)
    pairs = data.dropna(subset=["previous_pitch", "pitch_type"])
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in pairs.itertuples(index=False):
        counts[str(row.previous_pitch)][str(row.pitch_type)] += 1
    rows=[]
    for previous, counter in counts.items():
        total=sum(counter.values())
        nxt, n=counter.most_common(1)[0]
        rows.append({"previous_pitch": previous, "next_pitch": nxt, "probability": round(n/total*100,1), "sample": total})
    return sorted(rows, key=lambda r:r["sample"], reverse=True)[:10]



def _offensive_attack_plan(arsenal: list[dict[str, Any]]) -> list[str]:
    """Translate scouting metrics into concise hitter-facing guidance."""
    if not arsenal:
        return []
    attackable = sorted(
        arsenal,
        key=lambda p: (float(p.get("xwoba_allowed") or 0.0), float(p.get("usage_rate") or 0.0)),
        reverse=True,
    )
    best_chase = max(arsenal, key=lambda p: float(p.get("chase_rate") or 0.0))
    best_whiff = max(arsenal, key=lambda p: float(p.get("whiff_rate") or 0.0))
    primary = attackable[0]
    plan = [
        f"Damage opportunity: be ready for {primary.get('pitch_name', primary.get('pitch_type'))} in the strike zone; it has allowed {float(primary.get('xwoba_allowed') or 0):.3f} xwOBA.",
        f"Chase warning: lay off {best_chase.get('pitch_name', best_chase.get('pitch_type'))} when it starts below or off the plate ({float(best_chase.get('chase_rate') or 0):.1f}% chase rate).",
        f"Two-strike protection: shorten against {best_whiff.get('pitch_name', best_whiff.get('pitch_type'))}, the top bat-missing pitch ({float(best_whiff.get('whiff_rate') or 0):.1f}% whiff rate).",
    ]
    return plan


def build_opponent_pitcher_scout(metadata: dict[str, Any], pitches: pd.DataFrame) -> dict[str, Any]:
    arsenal = summarize_pitcher_arsenal(pitches)
    strengths, weaknesses = _strengths_and_weaknesses(arsenal)
    flags = add_flags(pitches)
    overall = {
        "pitch_count": len(flags),
        "whiff_rate": round(float(flags["is_whiff"].sum()) / max(1, int(flags["is_swing"].sum())) * 100, 1),
        "chase_rate": round(float(flags["is_chase"].sum()) / max(1, int((~flags["is_in_zone"]).sum())) * 100, 1),
        "zone_rate": round(float(flags["is_in_zone"].mean()) * 100, 1) if len(flags) else 0.0,
    }
    return {"pitcher": metadata, "overall": overall, "arsenal": arsenal,
            "strengths": strengths, "weaknesses": weaknesses,
            "usage_by_count": _usage_by_count(pitches),
            "transitions": _transitions(pitches),
            "offensive_attack_plan": _offensive_attack_plan(arsenal),
            "heatmaps": build_location_heatmaps(pitches, PITCH_NAMES)}
