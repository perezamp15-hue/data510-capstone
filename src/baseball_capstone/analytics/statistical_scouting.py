"""Database-backed statistical scouting analysis for two MLB teams.

This module intentionally uses descriptive statistics and empirical
probabilities. It does not load or score machine-learning models.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from math import sqrt
from typing import Any, Iterable, Sequence

import pandas as pd
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.engine import Engine


SWING_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "foul",
    "foul_tip",
    "foul_bunt",
    "missed_bunt",
    "hit_into_play",
    "in_play",
}
WHIFF_DESCRIPTIONS = {
    "swinging_strike",
    "swinging_strike_blocked",
    "missed_bunt",
}
CALLED_STRIKE_DESCRIPTIONS = {"called_strike"}
BALL_DESCRIPTIONS = {
    "ball",
    "blocked_ball",
    "pitchout",
    "intent_ball",
    "automatic_ball",
}
CONTACT_DESCRIPTIONS = SWING_DESCRIPTIONS - WHIFF_DESCRIPTIONS
HIT_EVENTS = {"single", "double", "triple", "home_run"}
WALK_EVENTS = {"walk", "intent_walk"}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
OUT_EVENTS = {
    "field_out",
    "force_out",
    "grounded_into_double_play",
    "double_play",
    "triple_play",
    "fielders_choice_out",
    "sac_fly",
    "sac_bunt",
    "strikeout",
    "strikeout_double_play",
}
PITCH_NAMES = {
    "FF": "Four-Seam Fastball",
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
    "SV": "Slurve",
}


@dataclass(frozen=True)
class PlayerIdentity:
    player_id: int
    full_name: str
    bats: str | None
    throws: str | None
    primary_position: str | None
    position_name: str | None
    current_team: str | None


class PlayerLookupError(ValueError):
    """Raised when a player name is missing or ambiguous."""


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _pct(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return 100.0 * float(numerator) / float(denominator)


def _rate(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return float(numerator) / float(denominator)


def _display_pitch_name(code: Any, name: Any = None) -> str:
    if isinstance(name, str) and name.strip():
        return name.strip()
    if isinstance(code, str) and code.strip():
        clean = code.strip().upper()
        return PITCH_NAMES.get(clean, clean)
    return "Unknown"


def _normalize_text(series: pd.Series) -> pd.Series:
    """Normalize event labels from either snake_case or display text."""
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )


def _scouting_grade(value: float | None, *, low: float, high: float, inverse: bool = False) -> int | None:
    """Map a metric to a traditional 20-80 scouting grade in five-point steps."""
    if value is None or pd.isna(value):
        return None
    if high <= low:
        return 50
    ratio = (float(value) - low) / (high - low)
    if inverse:
        ratio = 1.0 - ratio
    ratio = max(0.0, min(1.0, ratio))
    return int(round((20.0 + ratio * 60.0) / 5.0) * 5)


def _zone_grid(rows: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    lookup = {int(row["zone"]): row for row in rows if int(row.get("zone", 0)) in range(1, 10)}
    output = []
    for zone in range(1, 10):
        row = lookup.get(zone, {})
        output.append({
            "zone": zone,
            "label": zone_label(zone),
            "value": row.get(metric),
            "pitches": int(row.get("pitches", 0) or 0),
        })
    return output


def _batted_ball_profile(sample: pd.DataFrame) -> dict[str, Any]:
    batted = sample.loc[sample["launch_angle"].notna()].copy()
    if batted.empty:
        return {"sample": 0, "ground_ball_pct": None, "line_drive_pct": None, "fly_ball_pct": None, "popup_pct": None}
    angle = batted["launch_angle"]
    return {
        "sample": int(len(batted)),
        "ground_ball_pct": _pct((angle < 10).sum(), len(batted)),
        "line_drive_pct": _pct(angle.between(10, 25, inclusive="left").sum(), len(batted)),
        "fly_ball_pct": _pct(angle.between(25, 50, inclusive="left").sum(), len(batted)),
        "popup_pct": _pct((angle >= 50).sum(), len(batted)),
    }


def _normalize_person_name(value: str) -> str:
    """Normalize a player name for accent- and punctuation-tolerant matching."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    normalized = normalized.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def resolve_team(engine: Engine, team_name: str) -> dict[str, Any]:
    """Resolve one MLB team by its full name or abbreviation."""
    clean_name = " ".join(team_name.split()).strip()
    if len(clean_name) < 2:
        raise PlayerLookupError("Team name must contain at least two characters.")

    query = text(
        """
        SELECT team_id, name, abbreviation
        FROM teams
        WHERE lower(name) = lower(:team_name)
           OR lower(coalesce(abbreviation, '')) = lower(:team_name)
        ORDER BY active DESC, name
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query, {"team_name": clean_name}).mappings().all()

    unique_rows = {int(row["team_id"]): row for row in rows}
    if not unique_rows:
        raise PlayerLookupError(f'No team found for "{clean_name}".')
    if len(unique_rows) > 1:
        choices = ", ".join(
            f'{row["name"]} ({row["abbreviation"] or row["team_id"]})'
            for row in unique_rows.values()
        )
        raise PlayerLookupError(f'Ambiguous team "{clean_name}". Matches: {choices}')
    return dict(next(iter(unique_rows.values())))


def _player_aliases(row: Any) -> set[str]:
    """Return normalized names that may identify one player row."""
    values = {
        row.get("full_name"),
        row.get("use_name"),
        " ".join(
            part for part in (row.get("first_name"), row.get("last_name")) if part
        ),
    }
    return {_normalize_person_name(str(value)) for value in values if value}


def _matches_player_role(row: Any, role: str) -> bool:
    """Use roster position metadata to separate hitters from pitchers."""
    primary = str(row.get("primary_position") or "").strip().upper()
    position_name = str(row.get("position_name") or "").strip().casefold()
    position_type = str(row.get("position_type") or "").strip().casefold()
    is_pitcher = primary == "P" or "pitcher" in position_name or "pitcher" in position_type

    if role == "pitcher":
        return is_pitcher
    if role == "batter":
        return not is_pitcher
    return True


def resolve_player(
    engine: Engine,
    player_name: str,
    team_name: str,
    *,
    role: str = "any",
) -> PlayerIdentity:
    """Resolve a player using team first, then a safe league-wide fallback.

    The ``players.current_team_id`` field represents the latest roster snapshot.
    It can be stale or can exclude an injured/minor-league player who still has
    valid Statcast history in the requested report period. Therefore resolution
    follows this order:

    1. Exact normalized name on the requested current roster.
    2. Exact normalized name league-wide, filtered by expected role.
    3. Partial normalized name on the requested roster.
    4. Partial normalized name league-wide, filtered by expected role.

    The role filter distinguishes duplicate names such as catcher Will Smith and
    pitcher Will Smith. Team matching still resolves duplicate hitters such as
    the two players named Max Muncy whenever roster data is available.
    """
    clean_name = " ".join(player_name.split()).strip()
    if len(clean_name) < 2:
        raise PlayerLookupError("Player name must contain at least two characters.")
    if role not in {"any", "pitcher", "batter"}:
        raise ValueError(f"Unsupported player role: {role}")

    team = resolve_team(engine, team_name)
    query = text(
        """
        SELECT
            p.player_id,
            p.full_name,
            p.use_name,
            p.first_name,
            p.last_name,
            p.bats,
            p.throws,
            p.primary_position,
            p.position_name,
            p.position_type,
            p.active,
            p.current_team_id,
            t.name AS current_team
        FROM players p
        LEFT JOIN teams t ON t.team_id = p.current_team_id
        ORDER BY p.active DESC, p.full_name, p.player_id
        """
    )
    with engine.connect() as connection:
        rows = connection.execute(query).mappings().all()

    target = _normalize_person_name(clean_name)
    team_id = int(team["team_id"])
    team_rows = [row for row in rows if row.get("current_team_id") == team_id]

    def exact_matches(pool: Sequence[Any]) -> list[Any]:
        return [row for row in pool if target in _player_aliases(row)]

    def partial_matches(pool: Sequence[Any]) -> list[Any]:
        return [
            row
            for row in pool
            if any(alias.startswith(target) or target in alias for alias in _player_aliases(row))
        ]

    candidate_groups = [
        exact_matches(team_rows),
        [row for row in exact_matches(rows) if _matches_player_role(row, role)],
        partial_matches(team_rows),
        [row for row in partial_matches(rows) if _matches_player_role(row, role)],
    ]

    candidates: list[Any] = []
    for group in candidate_groups:
        unique_group = {int(row["player_id"]): row for row in group}
        if unique_group:
            candidates = list(unique_group.values())
            break

    if not candidates:
        roster_preview = ", ".join(str(row["full_name"]) for row in team_rows[:12])
        suffix = f" Current roster examples: {roster_preview}." if roster_preview else ""
        raise PlayerLookupError(
            f'No {role if role != "any" else "player"} named "{clean_name}" was found '
            f'for "{team["name"]}" or in the league-wide fallback.{suffix}'
        )

    if len(candidates) > 1:
        choices = ", ".join(
            f'{row["full_name"]} ({row["player_id"]}, '
            f'{row.get("position_name") or row.get("primary_position") or "position unknown"}, '
            f'{row.get("current_team") or "team unknown"})'
            for row in candidates
        )
        raise PlayerLookupError(
            f'Ambiguous player name "{clean_name}" for role "{role}". Matches: {choices}. '
            "Use the exact stored full name and verify the player position metadata."
        )

    row = candidates[0]
    return PlayerIdentity(
        player_id=int(row["player_id"]),
        full_name=str(row["full_name"]),
        bats=row["bats"],
        throws=row["throws"],
        primary_position=row["primary_position"],
        position_name=row["position_name"],
        current_team=row["current_team"] or str(team["name"]),
    )


def resolve_lineup(
    engine: Engine,
    names: Sequence[str],
    team_name: str,
) -> list[PlayerIdentity]:
    """Resolve exactly nine unique hitters, preferring the requested roster."""
    clean_names = [name.strip() for name in names if name.strip()]
    if len(clean_names) != 9:
        raise ValueError(f"A lineup must contain exactly nine names; received {len(clean_names)}.")
    players = [
        resolve_player(engine, name, team_name, role="batter")
        for name in clean_names
    ]
    duplicates = [
        pid
        for pid, count in Counter(player.player_id for player in players).items()
        if count > 1
    ]
    if duplicates:
        raise ValueError(f"The lineup contains duplicate player IDs: {duplicates}")
    return players

def load_pitch_data(
    engine: Engine,
    *,
    pitcher_ids: Sequence[int],
    batter_ids: Sequence[int],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Load only pitches needed for the two pitchers and two lineups."""
    available_columns = {column["name"] for column in inspect(engine).get_columns("pitches")}
    optional_hc_x = "p.hc_x" if "hc_x" in available_columns else "NULL::double precision AS hc_x"
    optional_hc_y = "p.hc_y" if "hc_y" in available_columns else "NULL::double precision AS hc_y"

    query = text(
        f"""
        SELECT
            p.pitch_id,
            p.game_pk,
            p.game_date,
            p.at_bat_number,
            p.plate_appearance_number,
            p.pitch_number,
            p.inning,
            p.inning_half,
            p.outs,
            p.balls,
            p.strikes,
            p.pitcher_id,
            p.batter_id,
            p.pitch_type,
            p.pitch_name,
            p.description,
            p.event,
            p.event_type,
            p.is_ball,
            p.is_strike,
            p.is_in_play,
            p.release_speed,
            p.release_spin_rate,
            p.release_extension,
            p.release_pos_x,
            p.release_pos_z,
            p.plate_x,
            p.plate_z,
            p.strike_zone_top,
            p.strike_zone_bottom,
            p.pfx_x,
            p.pfx_z,
            p.launch_speed,
            p.launch_angle,
            p.hit_distance,
            {optional_hc_x},
            {optional_hc_y},
            p.estimated_batting_average,
            p.estimated_slugging,
            p.zone
        FROM pitches p
        WHERE p.game_date BETWEEN :start_date AND :end_date
          AND (
            p.pitcher_id IN :pitcher_ids
            OR p.batter_id IN :batter_ids
          )
        ORDER BY p.game_date, p.game_pk, p.at_bat_number, p.pitch_number
        """
    ).bindparams(
        bindparam("pitcher_ids", expanding=True),
        bindparam("batter_ids", expanding=True),
    )
    frame = pd.read_sql_query(
        query,
        engine,
        params={
            "start_date": start_date,
            "end_date": end_date,
            "pitcher_ids": list(dict.fromkeys(int(v) for v in pitcher_ids)),
            "batter_ids": list(dict.fromkeys(int(v) for v in batter_ids)),
        },
    )
    if frame.empty:
        return frame

    frame = frame.copy()
    frame["game_date"] = pd.to_datetime(frame["game_date"], errors="coerce")
    for column in (
        "release_speed",
        "release_spin_rate",
        "release_extension",
        "release_pos_x",
        "release_pos_z",
        "plate_x",
        "plate_z",
        "strike_zone_top",
        "strike_zone_bottom",
        "pfx_x",
        "pfx_z",
        "launch_speed",
        "launch_angle",
        "hit_distance",
        "hc_x",
        "hc_y",
        "estimated_batting_average",
        "estimated_slugging",
    ):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["description_norm"] = _normalize_text(frame["description"])
    frame["event_norm"] = _normalize_text(frame["event"].where(frame["event"].notna(), frame["event_type"]))
    frame["is_swing"] = frame["description_norm"].isin(SWING_DESCRIPTIONS)
    frame["is_whiff"] = frame["description_norm"].isin(WHIFF_DESCRIPTIONS)
    frame["is_called_strike"] = frame["description_norm"].isin(CALLED_STRIKE_DESCRIPTIONS)
    frame["is_contact"] = frame["description_norm"].isin(CONTACT_DESCRIPTIONS)
    frame["is_ball_result"] = frame["description_norm"].isin(BALL_DESCRIPTIONS)
    frame["is_hard_hit"] = frame["launch_speed"].ge(95.0)
    frame["is_sweet_spot"] = frame["launch_angle"].between(8.0, 32.0, inclusive="both")
    frame["pitch_label"] = [
        _display_pitch_name(code, name)
        for code, name in zip(frame["pitch_type"], frame["pitch_name"], strict=False)
    ]
    return frame


def _plate_appearance_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one terminal row per plate appearance when terminal events exist."""
    if frame.empty:
        return frame.copy()
    candidates = frame.loc[frame["event_norm"].ne("")].copy()
    if candidates.empty:
        return candidates
    candidates = candidates.sort_values(["game_pk", "at_bat_number", "pitch_number"])
    return candidates.groupby(["game_pk", "at_bat_number"], as_index=False).tail(1)


def pitcher_summary(frame: pd.DataFrame, pitcher: PlayerIdentity) -> dict[str, Any]:
    sample = frame.loc[frame["pitcher_id"].eq(pitcher.player_id)].copy()
    pitches = int(len(sample))
    swings = int(sample["is_swing"].sum()) if pitches else 0
    whiffs = int(sample["is_whiff"].sum()) if pitches else 0
    contact = int(sample["is_contact"].sum()) if pitches else 0
    balls_in_play = int(sample["is_in_play"].fillna(False).sum()) if pitches else 0
    strikes = int(sample["is_strike"].fillna(False).sum()) if pitches else 0
    called_plus_whiff = int((sample["is_called_strike"] | sample["is_whiff"]).sum()) if pitches else 0
    zone_pitches = int(sample["zone"].between(1, 9, inclusive="both").sum()) if pitches else 0
    chase_mask = sample["zone"].notna() & ~sample["zone"].between(1, 9, inclusive="both") & sample["is_swing"]
    outside = int((sample["zone"].notna() & ~sample["zone"].between(1, 9, inclusive="both")).sum()) if pitches else 0

    pa = _plate_appearance_results(sample)
    hits = int(pa["event_norm"].isin(HIT_EVENTS).sum()) if not pa.empty else 0
    walks = int(pa["event_norm"].isin(WALK_EVENTS).sum()) if not pa.empty else 0
    strikeouts = int(pa["event_norm"].isin(STRIKEOUT_EVENTS).sum()) if not pa.empty else 0
    outs_recorded = int(pa["event_norm"].isin(OUT_EVENTS).sum()) if not pa.empty else 0
    innings_estimate = outs_recorded / 3.0 if outs_recorded else None
    whip_estimate = (hits + walks) / innings_estimate if innings_estimate else None

    first_pitch = sample.loc[sample["pitch_number"].eq(1)]
    batted = sample.loc[sample["launch_speed"].notna()]

    return {
        "identity": asdict(pitcher),
        "sample": {
            "pitches": pitches,
            "games": int(sample["game_pk"].nunique()) if pitches else 0,
            "batters_faced": int(sample["batter_id"].nunique()) if pitches else 0,
            "plate_appearances_with_result": int(len(pa)),
        },
        "traditional_estimates": {
            "hits_allowed": hits,
            "walks": walks,
            "strikeouts": strikeouts,
            "outs_recorded_from_events": outs_recorded,
            "innings_estimate": innings_estimate,
            "whip_estimate": whip_estimate,
            "era": None,
            "era_note": "Official ERA is not calculated because earned-run attribution is not stored in the current pitch table.",
        },
        "rates": {
            "strike_rate": _pct(strikes, pitches),
            "first_pitch_strike_rate": _pct(first_pitch["is_strike"].fillna(False).sum(), len(first_pitch)),
            "swing_rate": _pct(swings, pitches),
            "whiff_rate_per_swing": _pct(whiffs, swings),
            "contact_rate_per_swing": _pct(contact, swings),
            "csw_rate": _pct(called_plus_whiff, pitches),
            "zone_rate": _pct(zone_pitches, int(sample["zone"].notna().sum())),
            "chase_rate": _pct(int(chase_mask.sum()), outside),
            "in_play_rate": _pct(balls_in_play, pitches),
            "hard_hit_rate": _pct(batted["is_hard_hit"].sum(), len(batted)),
            "sweet_spot_rate": _pct(batted["is_sweet_spot"].sum(), len(batted)),
        },
        "averages": {
            "release_speed": _safe_float(sample["release_speed"].mean()),
            "spin_rate": _safe_float(sample["release_spin_rate"].mean()),
            "extension": _safe_float(sample["release_extension"].mean()),
            "exit_velocity": _safe_float(batted["launch_speed"].mean()),
            "launch_angle": _safe_float(batted["launch_angle"].mean()),
            "xBA": _safe_float(sample["estimated_batting_average"].mean()),
            "xSLG": _safe_float(sample["estimated_slugging"].mean()),
        },
        "arsenal": pitcher_arsenal(sample),
        "count_tendencies": pitch_probabilities(sample, group_columns=("balls", "strikes"), minimum_sample=1),
        "handedness_tendencies": [],
    }


def pitcher_arsenal(sample: pd.DataFrame) -> list[dict[str, Any]]:
    if sample.empty:
        return []
    total = len(sample)
    rows: list[dict[str, Any]] = []
    for label, group in sample.groupby("pitch_label", dropna=False):
        swings = int(group["is_swing"].sum())
        batted = group.loc[group["launch_speed"].notna()]
        rows.append(
            {
                "pitch": str(label),
                "count": int(len(group)),
                "usage_pct": _pct(len(group), total),
                "avg_velocity": _safe_float(group["release_speed"].mean()),
                "avg_spin": _safe_float(group["release_spin_rate"].mean()),
                "avg_extension": _safe_float(group["release_extension"].mean()),
                "strike_pct": _pct(group["is_strike"].fillna(False).sum(), len(group)),
                "whiff_pct": _pct(group["is_whiff"].sum(), swings),
                "zone_pct": _pct(group["zone"].between(1, 9, inclusive="both").sum(), group["zone"].notna().sum()),
                "chase_pct": _pct(
                    (group["is_swing"] & group["zone"].notna() & ~group["zone"].between(1, 9, inclusive="both")).sum(),
                    (group["zone"].notna() & ~group["zone"].between(1, 9, inclusive="both")).sum(),
                ),
                "put_away_pct": _pct(
                    (group["is_whiff"] & group["strikes"].eq(2)).sum(),
                    group["strikes"].eq(2).sum(),
                ),
                "release_height": _safe_float(group["release_pos_z"].mean()),
                "hard_hit_pct": _pct(batted["is_hard_hit"].sum(), len(batted)),
                "avg_exit_velocity": _safe_float(batted["launch_speed"].mean()),
                "horizontal_break": _safe_float(group["pfx_x"].mean()),
                "vertical_break": _safe_float(group["pfx_z"].mean()),
                "grade": _scouting_grade(
                    (_pct(group["is_whiff"].sum(), swings) or 0) * 0.55
                    + (_pct(group["is_strike"].fillna(False).sum(), len(group)) or 0) * 0.25
                    + (100 - (_pct(batted["is_hard_hit"].sum(), len(batted)) or 40)) * 0.20,
                    low=20, high=65,
                ),
                "location_grid": _zone_grid(batter_zone_performance(group), "usage_pct") if False else [],
            }
        )
    return sorted(rows, key=lambda row: row["count"], reverse=True)


def batter_summary(frame: pd.DataFrame, batter: PlayerIdentity) -> dict[str, Any]:
    sample = frame.loc[frame["batter_id"].eq(batter.player_id)].copy()
    pitches = len(sample)
    swings = int(sample["is_swing"].sum()) if pitches else 0
    whiffs = int(sample["is_whiff"].sum()) if pitches else 0
    batted = sample.loc[sample["launch_speed"].notna()]
    pa = _plate_appearance_results(sample)
    hits = int(pa["event_norm"].isin(HIT_EVENTS).sum()) if not pa.empty else 0
    walks = int(pa["event_norm"].isin(WALK_EVENTS).sum()) if not pa.empty else 0
    strikeouts = int(pa["event_norm"].isin(STRIKEOUT_EVENTS).sum()) if not pa.empty else 0
    at_bats = int(len(pa) - walks) if not pa.empty else 0
    batting_average = _rate(hits, at_bats)
    on_base = _rate(hits + walks, len(pa))

    return {
        "identity": asdict(batter),
        "sample": {
            "pitches": int(pitches),
            "games": int(sample["game_pk"].nunique()) if pitches else 0,
            "plate_appearances_with_result": int(len(pa)),
        },
        "traditional_estimates": {
            "hits": hits,
            "walks": walks,
            "strikeouts": strikeouts,
            "at_bats_estimate": at_bats,
            "batting_average_estimate": batting_average,
            "on_base_rate_estimate": on_base,
        },
        "rates": {
            "swing_rate": _pct(swings, pitches),
            "whiff_rate_per_swing": _pct(whiffs, swings),
            "contact_rate_per_swing": _pct(sample["is_contact"].sum(), swings),
            "strike_rate_seen": _pct(sample["is_strike"].fillna(False).sum(), pitches),
            "chase_rate": _pct(
                (sample["is_swing"] & ~sample["zone"].between(1, 9, inclusive="both")).sum(),
                (~sample["zone"].between(1, 9, inclusive="both") & sample["zone"].notna()).sum(),
            ),
            "hard_hit_rate": _pct(batted["is_hard_hit"].sum(), len(batted)),
            "csw_rate_seen": _pct((sample["is_called_strike"] | sample["is_whiff"]).sum(), pitches),
        },
        "averages": {
            "exit_velocity": _safe_float(batted["launch_speed"].mean()),
            "launch_angle": _safe_float(batted["launch_angle"].mean()),
            "xBA": _safe_float(sample["estimated_batting_average"].mean()),
            "xSLG": _safe_float(sample["estimated_slugging"].mean()),
        },
        "pitch_type_performance": batter_pitch_type_performance(sample),
        "zone_performance": batter_zone_performance(sample),
        "batted_ball_profile": _batted_ball_profile(sample),
    }


def batter_pitch_type_performance(sample: pd.DataFrame) -> list[dict[str, Any]]:
    if sample.empty:
        return []
    rows = []
    for label, group in sample.groupby("pitch_label", dropna=False):
        swings = int(group["is_swing"].sum())
        batted = group.loc[group["launch_speed"].notna()]
        rows.append(
            {
                "pitch": str(label),
                "pitches": int(len(group)),
                "usage_seen_pct": _pct(len(group), len(sample)),
                "swing_pct": _pct(swings, len(group)),
                "whiff_pct": _pct(group["is_whiff"].sum(), swings),
                "strike_pct": _pct(group["is_strike"].fillna(False).sum(), len(group)),
                "hard_hit_pct": _pct(batted["is_hard_hit"].sum(), len(batted)),
                "avg_exit_velocity": _safe_float(batted["launch_speed"].mean()),
            }
        )
    return sorted(rows, key=lambda row: row["pitches"], reverse=True)


def batter_zone_performance(sample: pd.DataFrame) -> list[dict[str, Any]]:
    if sample.empty:
        return []
    rows = []
    for zone, group in sample.loc[sample["zone"].notna()].groupby("zone"):
        swings = int(group["is_swing"].sum())
        batted = group.loc[group["launch_speed"].notna()]
        rows.append(
            {
                "zone": int(zone),
                "label": zone_label(int(zone)),
                "pitches": int(len(group)),
                "usage_pct": _pct(len(group), len(sample)),
                "swing_pct": _pct(swings, len(group)),
                "whiff_pct": _pct(group["is_whiff"].sum(), swings),
                "hard_hit_pct": _pct(batted["is_hard_hit"].sum(), len(batted)),
                "avg_exit_velocity": _safe_float(batted["launch_speed"].mean()),
            }
        )
    return sorted(rows, key=lambda row: row["zone"])


def zone_label(zone: int) -> str:
    labels = {
        1: "Upper-left third",
        2: "Upper-middle third",
        3: "Upper-right third",
        4: "Middle-left third",
        5: "Heart of zone",
        6: "Middle-right third",
        7: "Lower-left third",
        8: "Lower-middle third",
        9: "Lower-right third",
        11: "Above/left chase",
        12: "Above/right chase",
        13: "Below/left chase",
        14: "Below/right chase",
    }
    return labels.get(zone, f"Zone {zone}")


def pitch_probabilities(
    sample: pd.DataFrame,
    *,
    group_columns: Sequence[str] = ("balls", "strikes"),
    minimum_sample: int = 1,
) -> list[dict[str, Any]]:
    """Calculate empirical pitch mix for each requested context."""
    if sample.empty:
        return []
    usable = sample.loc[sample["pitch_label"].ne("Unknown")].copy()
    if usable.empty:
        return []
    output: list[dict[str, Any]] = []
    for keys, group in usable.groupby(list(group_columns), dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        if len(group) < minimum_sample:
            continue
        counts = group["pitch_label"].value_counts()
        context = {column: (None if pd.isna(value) else int(value) if isinstance(value, (int, float)) else value) for column, value in zip(group_columns, keys, strict=False)}
        output.append(
            {
                "context": context,
                "sample": int(len(group)),
                "pitches": [
                    {
                        "pitch": str(label),
                        "count": int(count),
                        "probability_pct": _pct(count, len(group)),
                        "wilson_low_pct": 100.0 * wilson_interval(count, len(group))[0],
                        "wilson_high_pct": 100.0 * wilson_interval(count, len(group))[1],
                    }
                    for label, count in counts.items()
                ],
            }
        )
    return output


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return ((centre - margin) / denominator, (centre + margin) / denominator)


def matchup_pitch_probabilities(
    pitcher_sample: pd.DataFrame,
    *,
    batter_id: int,
    important_counts: Iterable[tuple[int, int]] = ((0, 0), (0, 1), (1, 0), (1, 1), (1, 2), (2, 2), (3, 2)),
) -> list[dict[str, Any]]:
    """Empirical pitch probabilities with transparent sample fallback.

    Fallback order:
      1. exact pitcher-batter-count
      2. pitcher-count
      3. pitcher overall
    """
    results = []
    exact_batter = pitcher_sample.loc[pitcher_sample["batter_id"].eq(batter_id)]
    for balls, strikes in important_counts:
        exact = exact_batter.loc[exact_batter["balls"].eq(balls) & exact_batter["strikes"].eq(strikes)]
        count_only = pitcher_sample.loc[pitcher_sample["balls"].eq(balls) & pitcher_sample["strikes"].eq(strikes)]
        if len(exact) >= 8:
            selected = exact
            source = "Exact pitcher-batter-count history"
        elif len(count_only) >= 20:
            selected = count_only
            source = "Pitcher count tendency"
        else:
            selected = pitcher_sample
            source = "Pitcher overall tendency"
        counts = selected["pitch_label"].value_counts().head(5)
        results.append(
            {
                "count": f"{balls}-{strikes}",
                "source": source,
                "sample": int(len(selected)),
                "pitches": [
                    {
                        "pitch": str(label),
                        "count": int(value),
                        "probability_pct": _pct(value, len(selected)),
                        "interval": wilson_interval(int(value), len(selected)),
                    }
                    for label, value in counts.items()
                ],
            }
        )
    return results


def sequence_probabilities(
    pitcher_sample: pd.DataFrame,
    *,
    batter_id: int | None = None,
    minimum_exact_sequences: int = 8,
    limit: int = 8,
) -> dict[str, Any]:
    """Return empirical two-pitch transitions for a pitcher or matchup."""
    base = pitcher_sample.copy()
    source = "Pitcher overall sequence history"
    if batter_id is not None:
        exact = base.loc[base["batter_id"].eq(batter_id)]
        if len(exact) >= minimum_exact_sequences:
            base = exact
            source = "Exact pitcher-batter sequence history"
    if base.empty:
        return {"source": source, "sample": 0, "transitions": []}

    ordered = base.sort_values(["game_pk", "at_bat_number", "pitch_number"]).copy()
    ordered["next_pitch"] = ordered.groupby(["game_pk", "at_bat_number"])["pitch_label"].shift(-1)
    transitions = ordered.loc[ordered["next_pitch"].notna() & ordered["pitch_label"].ne("Unknown")]
    if transitions.empty:
        return {"source": source, "sample": 0, "transitions": []}

    pair_counts = transitions.groupby(["pitch_label", "next_pitch"]).size().rename("count").reset_index()
    origin_counts = transitions.groupby("pitch_label").size().to_dict()
    pair_counts["probability_pct"] = pair_counts.apply(
        lambda row: _pct(row["count"], origin_counts.get(row["pitch_label"], 0)), axis=1
    )
    pair_counts = pair_counts.sort_values(["count", "probability_pct"], ascending=False).head(limit)
    return {
        "source": source,
        "sample": int(len(transitions)),
        "transitions": [
            {
                "first_pitch": row.pitch_label,
                "next_pitch": row.next_pitch,
                "count": int(row.count),
                "conditional_probability_pct": float(row.probability_pct),
            }
            for row in pair_counts.itertuples(index=False)
        ],
    }


def _rolling_trends(sample: pd.DataFrame, *, role: str, window: int = 5, limit: int = 12) -> dict[str, Any]:
    """Return recent game-date metrics and five-appearance rolling averages.

    Baseball players do not necessarily appear on consecutive calendar days, so the
    window is calculated across the player's most recent appearance dates rather than
    filling off-days with zeros.
    """
    if sample.empty or sample["game_date"].dropna().empty:
        return {"window": window, "dates": [], "metrics": []}

    rows: list[dict[str, Any]] = []
    for game_date, group in sample.groupby(sample["game_date"].dt.date, sort=True):
        swings = int(group["is_swing"].sum())
        batted = group.loc[group["launch_speed"].notna()]
        row = {
            "date": game_date.isoformat(),
            "pitches": int(len(group)),
            "whiff_pct": _pct(group["is_whiff"].sum(), swings),
            "csw_pct": _pct((group["is_called_strike"] | group["is_whiff"]).sum(), len(group)),
            "strike_pct": _pct(group["is_strike"].fillna(False).sum(), len(group)),
            "hard_hit_pct": _pct(batted["is_hard_hit"].sum(), len(batted)),
            "avg_velocity": _safe_float(group["release_speed"].mean()),
            "avg_exit_velocity": _safe_float(batted["launch_speed"].mean()),
        }
        rows.append(row)

    daily = pd.DataFrame(rows)
    metric_defs = (
        [
            ("whiff_pct", "Whiff / swing", "%"),
            ("csw_pct", "CSW", "%"),
            ("strike_pct", "Strike rate", "%"),
            ("avg_velocity", "Average velocity", " mph"),
        ]
        if role == "pitcher"
        else [
            ("whiff_pct", "Whiff / swing", "%"),
            ("hard_hit_pct", "Hard-hit rate", "%"),
            ("avg_exit_velocity", "Average exit velocity", " mph"),
        ]
    )

    output_metrics: list[dict[str, Any]] = []
    for key, label, suffix in metric_defs:
        rolling = daily[key].rolling(window=window, min_periods=1).mean()
        recent = pd.DataFrame({"date": daily["date"], "value": rolling}).tail(limit)
        finite_values = [float(v) for v in recent["value"] if pd.notna(v)]
        low = min(finite_values) if finite_values else 0.0
        high = max(finite_values) if finite_values else 0.0
        span = high - low
        points = []
        for row in recent.itertuples(index=False):
            value = None if pd.isna(row.value) else float(row.value)
            height = 0.0 if value is None else (45.0 if span == 0 else 15.0 + 70.0 * (value - low) / span)
            points.append({"date": row.date, "value": value, "height": height})
        output_metrics.append({
            "key": key,
            "label": label,
            "suffix": suffix,
            "latest": finite_values[-1] if finite_values else None,
            "points": points,
        })

    return {
        "window": window,
        "dates": daily["date"].tail(limit).tolist(),
        "metrics": output_metrics,
        "appearance_dates": int(len(daily)),
    }


def _pitch_tunneling_proxy(sample: pd.DataFrame, *, minimum_pitches: int = 20, limit: int = 6) -> dict[str, Any]:
    """Rank pitch-pair tunneling proxies using available release and plate data.

    The current schema does not store full trajectory coefficients, so this is not a
    true decision-point or trajectory-overlap calculation. It rewards pitch pairs
    that share a similar average release point but separate later through plate
    location, movement, and velocity differences.
    """
    required = ["release_pos_x", "release_pos_z", "plate_x", "plate_z", "pfx_x", "pfx_z", "release_speed"]
    clean = sample.loc[sample["pitch_label"].ne("Unknown")].copy()
    if clean.empty:
        return {"available": False, "pairs": [], "note": "No pitch data available."}

    summaries: list[dict[str, Any]] = []
    for pitch, group in clean.groupby("pitch_label"):
        if len(group) < minimum_pitches:
            continue
        summaries.append({
            "pitch": str(pitch),
            "count": int(len(group)),
            **{column: _safe_float(group[column].mean()) for column in required},
        })

    pairs: list[dict[str, Any]] = []
    for i, first in enumerate(summaries):
        for second in summaries[i + 1:]:
            needed = [first.get(c) for c in required] + [second.get(c) for c in required]
            if any(v is None for v in needed):
                continue
            release_sep = sqrt((first["release_pos_x"] - second["release_pos_x"]) ** 2 + (first["release_pos_z"] - second["release_pos_z"]) ** 2) * 12.0
            plate_sep = sqrt((first["plate_x"] - second["plate_x"]) ** 2 + (first["plate_z"] - second["plate_z"]) ** 2) * 12.0
            movement_sep = sqrt((first["pfx_x"] - second["pfx_x"]) ** 2 + (first["pfx_z"] - second["pfx_z"]) ** 2) * 12.0
            velo_gap = abs(first["release_speed"] - second["release_speed"])

            release_component = max(0.0, 1.0 - release_sep / 10.0)
            late_separation_component = min(1.0, (plate_sep + 0.45 * movement_sep + 0.8 * velo_gap) / 30.0)
            raw_score = 0.58 * release_component + 0.42 * late_separation_component
            grade = int(round((20.0 + 60.0 * max(0.0, min(1.0, raw_score))) / 5.0) * 5)
            pairs.append({
                "pitch_one": first["pitch"],
                "pitch_two": second["pitch"],
                "count_one": first["count"],
                "count_two": second["count"],
                "release_separation_inches": release_sep,
                "plate_separation_inches": plate_sep,
                "movement_separation_inches": movement_sep,
                "velocity_gap_mph": velo_gap,
                "grade": max(20, min(80, grade)),
            })

    pairs.sort(key=lambda row: (row["grade"], -row["release_separation_inches"], row["plate_separation_inches"]), reverse=True)
    return {
        "available": bool(pairs),
        "pairs": pairs[:limit],
        "note": (
            "Tunneling proxy based on average release-point similarity and late separation at the plate. "
            "It is not a full trajectory or batter decision-point model because vx0/vy0/vz0 and ax/ay/az are not stored."
        ),
    }


def matchup_analysis(
    frame: pd.DataFrame,
    *,
    pitcher: PlayerIdentity,
    batter: PlayerIdentity,
    lineup_order: int,
) -> dict[str, Any]:
    pitcher_sample = frame.loc[frame["pitcher_id"].eq(pitcher.player_id)].copy()
    exact = pitcher_sample.loc[pitcher_sample["batter_id"].eq(batter.player_id)].copy()
    batter_all = frame.loc[frame["batter_id"].eq(batter.player_id)].copy()

    weakness_source = exact if len(exact) >= 20 else batter_all
    weakness_label = "Exact matchup" if len(exact) >= 20 else "Batter historical profile"
    pitch_perf = batter_pitch_type_performance(weakness_source)
    zone_perf = batter_zone_performance(weakness_source)

    weak_pitches = sorted(
        [row for row in pitch_perf if row["pitches"] >= 10],
        key=lambda row: (-(row["whiff_pct"] or 0), row["hard_hit_pct"] or 100),
    )[:3]
    damage_pitches = sorted(
        [row for row in pitch_perf if row["pitches"] >= 10],
        key=lambda row: (-(row["hard_hit_pct"] or 0), -(row["avg_exit_velocity"] or 0)),
    )[:3]
    weak_zones = sorted(
        [row for row in zone_perf if row["pitches"] >= 8],
        key=lambda row: (-(row["whiff_pct"] or 0), row["hard_hit_pct"] or 100),
    )[:3]
    damage_zones = sorted(
        [row for row in zone_perf if row["pitches"] >= 8],
        key=lambda row: (-(row["hard_hit_pct"] or 0), -(row["avg_exit_velocity"] or 0)),
    )[:3]

    confidence = confidence_label(len(exact), len(weakness_source))
    return {
        "lineup_order": lineup_order,
        "batter": asdict(batter),
        "pitcher": asdict(pitcher),
        "exact_matchup_pitches": int(len(exact)),
        "weakness_source": weakness_label,
        "weakness_sample": int(len(weakness_source)),
        "confidence": confidence,
        "batter_summary": batter_summary(frame, batter),
        "batter_tools": _batter_tools(batter_summary(frame, batter)),
        "rolling_trends": _rolling_trends(batter_all, role="batter"),
        "weak_pitches": weak_pitches,
        "damage_pitches": damage_pitches,
        "weak_zones": weak_zones,
        "damage_zones": damage_zones,
        "whiff_heatmap": _zone_grid(zone_perf, "whiff_pct"),
        "damage_heatmap": _zone_grid(zone_perf, "hard_hit_pct"),
        "pitcher_location_heatmap": _zone_grid(batter_zone_performance(pitcher_sample), "usage_pct"),
        "count_probabilities": matchup_pitch_probabilities(
            pitcher_sample,
            batter_id=batter.player_id,
        ),
        "sequences": sequence_probabilities(
            pitcher_sample,
            batter_id=batter.player_id,
        ),
        "strikeout_sequence": _common_strikeout_sequence(pitcher_sample, batter.player_id),
    }


def confidence_label(exact_sample: int, fallback_sample: int) -> dict[str, Any]:
    if exact_sample >= 75:
        label = "High"
    elif exact_sample >= 25:
        label = "Medium"
    elif fallback_sample >= 150:
        label = "Contextual"
    else:
        label = "Limited"
    stars = {"High": 5, "Medium": 4, "Contextual": 3, "Limited": 2}[label]
    score = min(100, int(round(min(exact_sample, 75) / 75 * 70 + min(fallback_sample, 500) / 500 * 30)))
    return {
        "label": label,
        "stars": stars,
        "score": score,
        "exact_sample": exact_sample,
        "fallback_sample": fallback_sample,
        "note": (
            "Confidence reflects historical sample size, not certainty about a future pitch or result."
        ),
    }



def _reference_percentile(value: float | None, low: float, high: float, inverse: bool = False) -> int | None:
    """Return a transparent reference-band percentile estimate, not a league leaderboard percentile."""
    if value is None or pd.isna(value) or high <= low:
        return None
    ratio = (float(value) - low) / (high - low)
    if inverse:
        ratio = 1.0 - ratio
    return int(round(max(0.0, min(1.0, ratio)) * 100))


def _pitcher_percentiles(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rates = profile["rates"]
    avgs = profile["averages"]
    return [
        {"label": "Whiff / swing", "value": rates.get("whiff_rate_per_swing"), "percentile": _reference_percentile(rates.get("whiff_rate_per_swing"), 15, 50)},
        {"label": "CSW", "value": rates.get("csw_rate"), "percentile": _reference_percentile(rates.get("csw_rate"), 20, 36)},
        {"label": "Chase", "value": rates.get("chase_rate"), "percentile": _reference_percentile(rates.get("chase_rate"), 18, 38)},
        {"label": "Zone", "value": rates.get("zone_rate"), "percentile": _reference_percentile(rates.get("zone_rate"), 38, 58)},
        {"label": "Hard hit allowed", "value": rates.get("hard_hit_rate"), "percentile": _reference_percentile(rates.get("hard_hit_rate"), 25, 55, inverse=True)},
        {"label": "Velocity", "value": avgs.get("release_speed"), "percentile": _reference_percentile(avgs.get("release_speed"), 86, 98)},
        {"label": "Extension", "value": avgs.get("extension"), "percentile": _reference_percentile(avgs.get("extension"), 5.2, 7.5)},
    ]


def _batter_tools(summary: dict[str, Any]) -> dict[str, int | None]:
    rates = summary["rates"]
    avgs = summary["averages"]
    return {
        "contact": _scouting_grade(rates.get("contact_rate_per_swing"), low=55, high=90),
        "power": _scouting_grade(rates.get("hard_hit_rate"), low=20, high=60),
        "discipline": _scouting_grade(rates.get("chase_rate"), low=15, high=45, inverse=True),
        "damage": _scouting_grade(avgs.get("exit_velocity"), low=82, high=96),
    }


def _spray_profile(sample: pd.DataFrame) -> dict[str, Any]:
    batted = sample.loc[sample["hc_x"].notna() & sample["hc_y"].notna()].copy()
    if batted.empty:
        return {"available": False, "sample": 0, "points": [], "pull_pct": None, "center_pct": None, "opposite_pct": None}
    # Baseball Savant field coordinates are centered near x=125. Split into three broad field sectors.
    batted["sector"] = pd.cut(batted["hc_x"], bins=[-float("inf"), 105, 145, float("inf")], labels=["left", "center", "right"])
    points = [
        {"x": float(row.hc_x), "y": float(row.hc_y)}
        for row in batted[["hc_x", "hc_y"]].itertuples(index=False)
    ]
    counts = batted["sector"].value_counts()
    return {
        "available": True,
        "sample": int(len(batted)),
        "points": points[:500],
        "left_pct": _pct(counts.get("left", 0), len(batted)),
        "center_pct": _pct(counts.get("center", 0), len(batted)),
        "right_pct": _pct(counts.get("right", 0), len(batted)),
    }


def _team_comparison(frame: pd.DataFrame, lineup: Sequence[PlayerIdentity]) -> dict[str, Any]:
    ids = [p.player_id for p in lineup]
    sample = frame.loc[frame["batter_id"].isin(ids)].copy()
    pa = _plate_appearance_results(sample)
    hits = int(pa["event_norm"].isin(HIT_EVENTS).sum()) if not pa.empty else 0
    walks = int(pa["event_norm"].isin(WALK_EVENTS).sum()) if not pa.empty else 0
    strikeouts = int(pa["event_norm"].isin(STRIKEOUT_EVENTS).sum()) if not pa.empty else 0
    at_bats = max(0, len(pa) - walks)
    batted = sample.loc[sample["launch_speed"].notna()]
    return {
        "pa": int(len(pa)),
        "avg": _rate(hits, at_bats),
        "obp": _rate(hits + walks, len(pa)),
        "strikeout_pct": _pct(strikeouts, len(pa)),
        "walk_pct": _pct(walks, len(pa)),
        "hard_hit_pct": _pct(batted["is_hard_hit"].sum(), len(batted)),
        "avg_exit_velocity": _safe_float(batted["launch_speed"].mean()),
    }


def _common_strikeout_sequence(sample: pd.DataFrame, batter_id: int) -> dict[str, Any] | None:
    exact = sample.loc[sample["batter_id"].eq(batter_id)].copy()
    if exact.empty:
        exact = sample.copy()
    sequences: Counter[tuple[str, ...]] = Counter()
    for _, group in exact.groupby(["game_pk", "at_bat_number"]):
        ordered = group.sort_values("pitch_number")
        terminal = ordered.tail(1)
        if terminal.empty or terminal.iloc[0]["event_norm"] not in STRIKEOUT_EVENTS:
            continue
        labels = tuple(ordered["pitch_label"].tail(3).tolist())
        if labels:
            sequences[labels] += 1
    if not sequences:
        return None
    sequence, count = sequences.most_common(1)[0]
    return {"pitches": list(sequence), "count": int(count), "sample": int(sum(sequences.values()))}


def _game_plan(pitcher_profile: dict[str, Any], matchups: list[dict[str, Any]]) -> dict[str, Any]:
    arsenal = pitcher_profile.get("arsenal", [])
    best_putaway = max(arsenal, key=lambda row: row.get("put_away_pct") or -1, default=None)
    most_used = arsenal[0] if arsenal else None
    dangerous = sorted(matchups, key=lambda m: (m["batter_summary"]["rates"].get("hard_hit_rate") or 0), reverse=True)
    vulnerable = sorted(matchups, key=lambda m: (m["batter_summary"]["rates"].get("whiff_rate_per_swing") or 0), reverse=True)
    return {
        "primary_pitch": most_used.get("pitch") if most_used else None,
        "putaway_pitch": best_putaway.get("pitch") if best_putaway else None,
        "dangerous_hitters": [m["batter"]["full_name"] for m in dangerous[:3]],
        "attack_hitters": [m["batter"]["full_name"] for m in vulnerable[:3]],
        "notes": [
            "Use red damage cells as avoid zones and red whiff cells as attack zones.",
            "Favor count tendencies only when their displayed sample is substantial.",
            "Treat exact-matchup sequences under 20 observations as descriptive rather than prescriptive.",
        ],
    }

def build_statistical_report(
    engine: Engine,
    *,
    our_team: str,
    opponent_team: str,
    our_pitcher_name: str,
    opposing_pitcher_name: str,
    our_lineup_names: Sequence[str],
    opponent_lineup_names: Sequence[str],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    # Resolve every player inside the team supplied on the command line.
    # This prevents same-name players on other MLB teams from being selected.
    our_pitcher = resolve_player(engine, our_pitcher_name, our_team, role="pitcher")
    opposing_pitcher = resolve_player(engine, opposing_pitcher_name, opponent_team, role="pitcher")
    our_lineup = resolve_lineup(engine, our_lineup_names, our_team)
    opponent_lineup = resolve_lineup(engine, opponent_lineup_names, opponent_team)

    frame = load_pitch_data(
        engine,
        pitcher_ids=[our_pitcher.player_id, opposing_pitcher.player_id],
        batter_ids=[p.player_id for p in our_lineup + opponent_lineup],
        start_date=start_date,
        end_date=end_date,
    )
    if frame.empty:
        raise RuntimeError("No pitch data was found for the selected players and date range.")

    our_pitcher_profile = pitcher_summary(frame, our_pitcher)
    opposing_pitcher_profile = pitcher_summary(frame, opposing_pitcher)

    our_pitcher_profile["percentiles"] = _pitcher_percentiles(our_pitcher_profile)
    opposing_pitcher_profile["percentiles"] = _pitcher_percentiles(opposing_pitcher_profile)
    our_pitcher_sample = frame.loc[frame["pitcher_id"].eq(our_pitcher.player_id)].copy()
    opposing_pitcher_sample = frame.loc[frame["pitcher_id"].eq(opposing_pitcher.player_id)].copy()
    our_pitcher_profile["pitch_tunneling"] = _pitch_tunneling_proxy(our_pitcher_sample)
    opposing_pitcher_profile["pitch_tunneling"] = _pitch_tunneling_proxy(opposing_pitcher_sample)
    our_pitcher_profile["rolling_trends"] = _rolling_trends(our_pitcher_sample, role="pitcher")
    opposing_pitcher_profile["rolling_trends"] = _rolling_trends(opposing_pitcher_sample, role="pitcher")

    executive_summary = {
        "opposing_primary_pitches": [row["pitch"] for row in opposing_pitcher_profile["arsenal"][:3]],
        "our_primary_pitches": [row["pitch"] for row in our_pitcher_profile["arsenal"][:3]],
        "opposing_whiff": opposing_pitcher_profile["rates"]["whiff_rate_per_swing"],
        "opposing_csw": opposing_pitcher_profile["rates"]["csw_rate"],
        "our_whiff": our_pitcher_profile["rates"]["whiff_rate_per_swing"],
        "our_csw": our_pitcher_profile["rates"]["csw_rate"],
    }

    our_offense = [
        matchup_analysis(
            frame,
            pitcher=opposing_pitcher,
            batter=batter,
            lineup_order=index,
        )
        for index, batter in enumerate(our_lineup, start=1)
    ]
    opponent_offense = [
        matchup_analysis(
            frame,
            pitcher=our_pitcher,
            batter=batter,
            lineup_order=index,
        )
        for index, batter in enumerate(opponent_lineup, start=1)
    ]

    return {
        "report_title": f"{our_team} vs. {opponent_team} Statistical Scouting Report",
        "our_team": our_team,
        "opponent_team": opponent_team,
        "data_period": f"{start_date.isoformat()} through {end_date.isoformat()}",
        "our_pitcher": our_pitcher_profile,
        "opposing_pitcher": opposing_pitcher_profile,
        "our_lineup": [asdict(player) for player in our_lineup],
        "opponent_lineup": [asdict(player) for player in opponent_lineup],
        "our_offense_matchups": our_offense,
        "opponent_offense_matchups": opponent_offense,
        "executive_summary": executive_summary,
        "our_team_comparison": _team_comparison(frame, our_lineup),
        "opponent_team_comparison": _team_comparison(frame, opponent_lineup),
        "our_game_plan": _game_plan(opposing_pitcher_profile, our_offense),
        "opponent_game_plan": _game_plan(our_pitcher_profile, opponent_offense),
        "methodology": [
            "Player names are resolved through the players dimension; IDs are used only internally.",
            "Pitch probabilities are observed historical frequencies, not machine-learning predictions.",
            "Count probabilities use exact matchup history when adequate, then fall back to pitcher count tendencies and pitcher overall tendencies.",
            "Pitch-sequence values are conditional frequencies for the next pitch after an observed pitch type.",
            "Batter weakness summaries use exact matchup data when at least 20 pitches are available; otherwise they use the batter's broader historical profile.",
            "Whiff rate uses swinging strikes divided by swings; CSW uses called strikes plus swinging strikes divided by all pitches.",
            "Heatmaps use Statcast zones 1-9 with chase-region summaries where available. Sparse cells display a dash and retain the pitch count.",
            "Percentile bars are transparent reference-band estimates, not official MLB leaderboard percentiles.",
            "Pitch grades are descriptive 20-80 grades based on whiff, strike, and contact-management components; they are not official scouting grades.",
            "Spray charts are intentionally omitted from this report; batted-ball quality is summarized with launch-angle and exit-velocity measures instead.",
            "Pitch tunneling is a proxy based on average release-point similarity and later separation in plate location, movement, and velocity. It is not a full trajectory-overlap model.",
            "Recent-trend charts use five-appearance-date rolling averages. Off-days are not inserted as zero-value observations.",
            "Estimated WHIP is derived from terminal pitch events and estimated outs. Official ERA is omitted because earned-run attribution is unavailable in the current pitch table.",
        ],
    }
