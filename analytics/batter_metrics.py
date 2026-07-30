from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

SWING_DESCRIPTIONS = {
    "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
    "foul_bunt", "hit_into_play",
}
WHIFF_DESCRIPTIONS = {"swinging_strike", "swinging_strike_blocked"}
CONTACT_DESCRIPTIONS = {"foul", "foul_tip", "foul_bunt", "hit_into_play"}
CALLED_STRIKE_DESCRIPTIONS = {"called_strike"}

HIT_EVENTS = {"single", "double", "triple", "home_run"}
WALK_EVENTS = {"walk", "intent_walk"}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
HBP_EVENTS = {"hit_by_pitch"}
SAC_FLY_EVENTS = {"sac_fly", "sac_fly_double_play"}
SAC_BUNT_EVENTS = {"sac_bunt", "sac_bunt_double_play"}
AT_BAT_EXCLUSIONS = WALK_EVENTS | HBP_EVENTS | SAC_FLY_EVENTS | SAC_BUNT_EVENTS | {
    "catcher_interf", "catcher_interference",
}

PITCH_NAMES = {
    "FF": "4-Seam", "SI": "Sinker", "FC": "Cutter", "SL": "Slider",
    "ST": "Sweeper", "CU": "Curveball", "KC": "Knuckle Curve",
    "CH": "Changeup", "FS": "Splitter", "FO": "Forkball",
    "KN": "Knuckleball", "EP": "Eephus",
}


def safe_percentage(numerator: Any, denominator: Any, decimals: int = 1) -> float:
    try:
        denominator_value = float(denominator)
        numerator_value = float(numerator)
    except (TypeError, ValueError):
        return 0.0
    if denominator_value <= 0 or not np.isfinite(denominator_value):
        return 0.0
    return round(numerator_value / denominator_value * 100.0, decimals)


def safe_mean(series: pd.Series, decimals: int = 1) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return round(float(numeric.mean()), decimals)


def normalized_text(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return warehouse text in a consistent Statcast-style snake_case form."""
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return (
        frame[column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def add_batter_flags(pitches: pd.DataFrame) -> pd.DataFrame:
    frame = pitches.copy()
    descriptions = normalized_text(frame, "pitch_description")
    events = normalized_text(frame, "events")

    frame["normalized_description"] = descriptions
    frame["normalized_event"] = events
    frame["is_swing"] = descriptions.isin(SWING_DESCRIPTIONS)
    frame["is_whiff"] = descriptions.isin(WHIFF_DESCRIPTIONS)
    frame["is_contact"] = descriptions.isin(CONTACT_DESCRIPTIONS)
    frame["is_called_strike"] = descriptions.isin(CALLED_STRIKE_DESCRIPTIONS)
    frame["is_in_play"] = descriptions.eq("hit_into_play")

    plate_x = numeric(frame, "plate_x")
    plate_z = numeric(frame, "plate_z")
    sz_top = numeric(frame, "sz_top")
    sz_bottom = numeric(frame, "sz_bottom")
    valid_zone = (
        plate_x.notna() & plate_z.notna() & sz_top.notna() & sz_bottom.notna()
        & sz_top.gt(sz_bottom)
    )
    frame["has_valid_zone"] = valid_zone
    frame["is_in_zone"] = (
        valid_zone
        & plate_x.between(-17.0 / 24.0, 17.0 / 24.0, inclusive="both")
        & plate_z.between(sz_bottom, sz_top, inclusive="both")
    )
    frame["is_out_of_zone"] = valid_zone & ~frame["is_in_zone"]
    frame["is_chase"] = frame["is_swing"] & frame["is_out_of_zone"]

    exit_velocity = numeric(frame, "exit_velocity")
    launch_angle = numeric(frame, "launch_angle")
    frame["is_batted_ball"] = frame["is_in_play"] & exit_velocity.notna()
    calculated_hard_hit = frame["is_batted_ball"] & exit_velocity.ge(95.0)
    calculated_sweet_spot = frame["is_batted_ball"] & launch_angle.between(8, 32)

    if "database_is_hard_hit" in frame.columns:
        stored = frame["database_is_hard_hit"].astype("boolean")
        frame["is_hard_hit"] = stored.where(stored.notna(), calculated_hard_hit).fillna(False)
        frame["is_hard_hit"] = frame["is_batted_ball"] & frame["is_hard_hit"].astype(bool)
    else:
        frame["is_hard_hit"] = calculated_hard_hit

    if "database_is_sweet_spot" in frame.columns:
        stored = frame["database_is_sweet_spot"].astype("boolean")
        frame["is_sweet_spot"] = stored.where(stored.notna(), calculated_sweet_spot).fillna(False)
        frame["is_sweet_spot"] = frame["is_batted_ball"] & frame["is_sweet_spot"].astype(bool)
    else:
        frame["is_sweet_spot"] = calculated_sweet_spot

    return frame


def plate_appearance_key_columns(frame: pd.DataFrame) -> list[str]:
    for columns in (["game_pk", "at_bat_number"], ["game_pk", "plate_appearance_number"]):
        if all(column in frame.columns for column in columns):
            return columns
    return [column for column in ["game_pk", "batter_id", "inning", "inning_half"] if column in frame.columns]


def get_terminal_plate_appearances(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    sort_columns = [
        column for column in [
            "game_date", "game_pk", "at_bat_number", "plate_appearance_number", "pitch_number"
        ] if column in frame.columns
    ]
    ordered = frame.sort_values(sort_columns) if sort_columns else frame.copy()
    keys = plate_appearance_key_columns(ordered)
    return ordered.groupby(keys, dropna=False, as_index=False).tail(1).copy() if keys else ordered.copy()


def calculate_batter_summary(pitches: pd.DataFrame) -> dict[str, Any]:
    frame = add_batter_flags(pitches)
    terminal = get_terminal_plate_appearances(frame)
    events = normalized_text(terminal, "events")

    pa = len(terminal)
    walks = int(events.isin(WALK_EVENTS).sum())
    hbp = int(events.isin(HBP_EVENTS).sum())
    sacrifice_flies = int(events.isin(SAC_FLY_EVENTS).sum())
    strikeouts = int(events.isin(STRIKEOUT_EVENTS).sum())
    hits = int(events.isin(HIT_EVENTS).sum())
    singles = int(events.eq("single").sum())
    doubles = int(events.eq("double").sum())
    triples = int(events.eq("triple").sum())
    home_runs = int(events.eq("home_run").sum())
    at_bats = int((events.ne("") & ~events.isin(AT_BAT_EXCLUSIONS)).sum())
    total_bases = singles + 2 * doubles + 3 * triples + 4 * home_runs

    batting_average = round(hits / at_bats, 3) if at_bats else None
    obp_denominator = at_bats + walks + hbp + sacrifice_flies
    obp = round((hits + walks + hbp) / obp_denominator, 3) if obp_denominator else None
    slugging = round(total_bases / at_bats, 3) if at_bats else None
    ops = round(obp + slugging, 3) if obp is not None and slugging is not None else None

    swing_count = int(frame["is_swing"].sum())
    whiff_count = int(frame["is_whiff"].sum())
    contact_count = int(frame["is_contact"].sum())
    in_zone = frame["is_in_zone"]
    out_zone = frame["is_out_of_zone"]
    batted = frame.loc[frame["is_batted_ball"]].copy()

    xwoba = safe_mean(numeric(frame, "expected_woba"), 3)
    xslg = safe_mean(numeric(frame, "expected_slugging"), 3)

    return {
        "game_count": int(frame["game_pk"].nunique()) if "game_pk" in frame else 0,
        "pitch_count": len(frame), "plate_appearances": pa, "at_bats": at_bats,
        "hits": hits, "singles": singles, "doubles": doubles, "triples": triples,
        "home_runs": home_runs, "walks": walks, "strikeouts": strikeouts, "hbp": hbp,
        "batting_average": batting_average, "on_base_percentage": obp,
        "slugging_percentage": slugging, "ops": ops,
        "walk_rate": safe_percentage(walks, pa), "strikeout_rate": safe_percentage(strikeouts, pa),
        "swing_rate": safe_percentage(swing_count, len(frame)),
        "whiff_rate": safe_percentage(whiff_count, swing_count),
        "contact_rate": safe_percentage(contact_count, swing_count),
        "zone_swing_rate": safe_percentage(int((frame["is_swing"] & in_zone).sum()), int(in_zone.sum())),
        "zone_contact_rate": safe_percentage(int((frame["is_contact"] & in_zone).sum()), int((frame["is_swing"] & in_zone).sum())),
        "chase_rate": safe_percentage(int(frame["is_chase"].sum()), int(out_zone.sum())),
        "chase_contact_rate": safe_percentage(int((frame["is_contact"] & out_zone).sum()), int((frame["is_swing"] & out_zone).sum())),
        "called_strike_rate": safe_percentage(int(frame["is_called_strike"].sum()), len(frame)),
        "average_exit_velocity": safe_mean(numeric(batted, "exit_velocity"), 1),
        "max_exit_velocity": (round(float(numeric(batted, "exit_velocity").max()), 1) if not batted.empty and numeric(batted, "exit_velocity").notna().any() else None),
        "average_launch_angle": safe_mean(numeric(batted, "launch_angle"), 1),
        "average_hit_distance": safe_mean(numeric(batted, "hit_distance"), 0),
        "hard_hit_rate": safe_percentage(int(batted["is_hard_hit"].sum()), len(batted)),
        "sweet_spot_rate": safe_percentage(int(batted["is_sweet_spot"].sum()), len(batted)),
        "xwoba": xwoba, "xslg": xslg,
    }


def calculate_pitch_type_performance(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    frame = add_batter_flags(pitches)
    records: list[dict[str, Any]] = []
    total = len(frame)
    for pitch_type, group in frame.loc[frame["pitch_type"].notna()].groupby("pitch_type"):
        terminal = get_terminal_plate_appearances(group)
        events = normalized_text(terminal, "events")
        at_bats = int((events.ne("") & ~events.isin(AT_BAT_EXCLUSIONS)).sum())
        hits = int(events.isin(HIT_EVENTS).sum())
        total_bases = int(events.eq("single").sum() + 2 * events.eq("double").sum() + 3 * events.eq("triple").sum() + 4 * events.eq("home_run").sum())
        swings = int(group["is_swing"].sum())
        out_zone = int(group["is_out_of_zone"].sum())
        batted = group.loc[group["is_batted_ball"]]
        records.append({
            "pitch_type": str(pitch_type), "pitch_name": PITCH_NAMES.get(str(pitch_type), str(pitch_type)),
            "pitch_count": len(group), "usage_percentage": safe_percentage(len(group), total),
            "average_velocity": safe_mean(numeric(group, "release_velocity"), 1),
            "swing_rate": safe_percentage(swings, len(group)),
            "whiff_rate": safe_percentage(int(group["is_whiff"].sum()), swings),
            "chase_rate": safe_percentage(int(group["is_chase"].sum()), out_zone),
            "batting_average": round(hits / at_bats, 3) if at_bats else None,
            "slugging_percentage": round(total_bases / at_bats, 3) if at_bats else None,
            "xwoba": safe_mean(numeric(group, "expected_woba"), 3),
            "average_exit_velocity": safe_mean(numeric(batted, "exit_velocity"), 1),
            "hard_hit_rate": safe_percentage(int(batted["is_hard_hit"].sum()), len(batted)),
        })
    return sorted(records, key=lambda row: row["pitch_count"], reverse=True)


def calculate_handedness_splits(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    frame = add_batter_flags(pitches)
    if "pitcher_throws" not in frame.columns:
        return []
    records = []
    for hand, group in frame.groupby(frame["pitcher_throws"].fillna("Unknown")):
        summary = calculate_batter_summary(group)
        records.append({"split": f"vs {str(hand).upper()}HP", **summary})
    return records


def calculate_count_splits(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    frame = add_batter_flags(pitches)
    if "ball_count" not in frame or "strike_count" not in frame:
        return []
    records = []
    for (balls, strikes), group in frame.groupby(["ball_count", "strike_count"], dropna=True):
        swings = int(group["is_swing"].sum())
        records.append({
            "count": f"{int(balls)}-{int(strikes)}", "pitches": len(group),
            "swing_rate": safe_percentage(swings, len(group)),
            "whiff_rate": safe_percentage(int(group["is_whiff"].sum()), swings),
            "xwoba": safe_mean(numeric(group, "expected_woba"), 3),
        })
    return sorted(records, key=lambda row: (int(row["count"][0]), int(row["count"][2])))
