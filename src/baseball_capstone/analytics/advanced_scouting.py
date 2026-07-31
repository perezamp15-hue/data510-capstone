"""Advanced scouting calculations for the matchup HTML report.

Adds four features without a Monte Carlo simulation:
1. Smoothed strike-zone heat maps.
2. Pitcher performance by inning.
3. Team offense overview with rolling averages.
4. Pitch release-point visualization over a mound diagram.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import Engine, text


IN_PLAY_EVENTS = {
    "single", "double", "triple", "home_run", "field_out", "force_out",
    "grounded_into_double_play", "field_error", "sac_fly", "sac_bunt",
    "fielders_choice", "fielders_choice_out", "double_play", "triple_play",
}
HIT_EVENTS = {"single", "double", "triple", "home_run"}
WALK_EVENTS = {"walk", "intent_walk"}
STRIKEOUT_EVENTS = {"strikeout", "strikeout_double_play"}
PA_EVENTS = IN_PLAY_EVENTS | HIT_EVENTS | WALK_EVENTS | STRIKEOUT_EVENTS | {
    "hit_by_pitch", "catcher_interf",
}
SWING_DESCRIPTIONS = {
    "swinging_strike", "swinging_strike_blocked", "foul", "foul_tip",
    "foul_bunt", "missed_bunt", "hit_into_play", "in_play",
}
WHIFF_DESCRIPTIONS = {
    "swinging_strike", "swinging_strike_blocked", "missed_bunt",
}


@dataclass(slots=True)
class AdvancedScoutingRepository:
    engine: Engine

    def pitcher_pitches(
        self,
        pitcher_id: int,
        season: int | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> pd.DataFrame:
        clauses = ["p.pitcher_id = :pitcher_id"]
        params: dict[str, Any] = {"pitcher_id": int(pitcher_id)}
        if season is not None:
            clauses.append("EXTRACT(YEAR FROM p.game_date) = :season")
            params["season"] = int(season)
        if start_date is not None:
            clauses.append("p.game_date >= :start_date")
            params["start_date"] = str(start_date)
        if end_date is not None:
            clauses.append("p.game_date <= :end_date")
            params["end_date"] = str(end_date)

        query = f"""
        SELECT
            p.game_pk,
            p.game_date,
            p.inning,
            p.at_bat_number,
            p.plate_appearance_number,
            p.pitch_number,
            p.batter_id,
            p.pitch_type,
            COALESCE(p.play_description, '') AS description,
            COALESCE(p.play_event, '') AS event,
            p.release_velocity,
            p.release_spin_rate,
            p.release_extension,
            p.release_pos_x,
            p.release_pos_y,
            p.release_pos_z,
            p.plate_crossing_x AS plate_x,
            p.plate_crossing_z AS plate_z,
            p.sz_top,
            p.sz_bot,
            p.exit_velocity,
            p.expected_woba,
            p.expected_slugging
        FROM public.statcast_pitches p
        WHERE {' AND '.join(clauses)}
        ORDER BY p.game_date, p.game_pk, p.at_bat_number, p.pitch_number
        """
        return pd.read_sql_query(text(query), self.engine, params=params)

    def team_batting_pitches(
        self,
        team_id: int,
        season: int | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> pd.DataFrame:
        clauses = [
            "((g.home_team_id = :team_id AND p.inning_half = 'bot') OR "
            " (g.away_team_id = :team_id AND p.inning_half = 'top'))"
        ]
        params: dict[str, Any] = {"team_id": int(team_id)}
        if season is not None:
            clauses.append("g.season = :season")
            params["season"] = int(season)
        if start_date is not None:
            clauses.append("p.game_date >= :start_date")
            params["start_date"] = str(start_date)
        if end_date is not None:
            clauses.append("p.game_date <= :end_date")
            params["end_date"] = str(end_date)

        query = f"""
        SELECT
            p.game_pk,
            p.game_date,
            p.at_bat_number,
            p.plate_appearance_number,
            p.pitch_number,
            p.batter_id,
            COALESCE(p.play_description, '') AS description,
            COALESCE(p.play_event, '') AS event,
            p.exit_velocity,
            p.expected_woba,
            p.expected_slugging,
            g.home_team_id,
            g.away_team_id,
            g.home_score,
            g.away_score
        FROM public.statcast_pitches p
        JOIN public.games g ON g.game_pk = p.game_pk
        WHERE {' AND '.join(clauses)}
        ORDER BY p.game_date, p.game_pk, p.at_bat_number, p.pitch_number
        """
        return pd.read_sql_query(text(query), self.engine, params=params)

    def team_name(self, team_id: int) -> str:
        query = text("""
            SELECT COALESCE(team_name, name, abbreviation, CAST(team_id AS text)) AS name
            FROM public.teams WHERE team_id = :team_id LIMIT 1
        """)
        try:
            frame = pd.read_sql_query(query, self.engine, params={"team_id": int(team_id)})
        except Exception:
            frame = pd.read_sql_query(
                text("SELECT COALESCE(name, abbreviation, CAST(team_id AS text)) AS name FROM public.teams WHERE team_id=:team_id LIMIT 1"),
                self.engine,
                params={"team_id": int(team_id)},
            )
        return str(frame.iloc[0]["name"]) if not frame.empty else str(team_id)

    def player_name(self, player_id: int) -> str:
        frame = pd.read_sql_query(
            text("SELECT COALESCE(full_name, CAST(player_id AS text)) AS name FROM public.players WHERE player_id=:player_id LIMIT 1"),
            self.engine,
            params={"player_id": int(player_id)},
        )
        return str(frame.iloc[0]["name"]) if not frame.empty else str(player_id)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _last_pitch_per_pa(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    keys = ["game_pk", "at_bat_number"]
    valid = frame.dropna(subset=["game_pk", "at_bat_number"]).copy()
    if valid.empty:
        return valid
    valid["pitch_number"] = _numeric(valid["pitch_number"]).fillna(0)
    return valid.sort_values(keys + ["pitch_number"]).groupby(keys, as_index=False).tail(1)


def build_inning_splits(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    """Summarize pitcher effectiveness and stuff by inning."""
    if pitches.empty or "inning" not in pitches:
        return []
    frame = pitches.copy()
    frame["inning"] = _numeric(frame["inning"])
    frame = frame[frame["inning"].between(1, 9, inclusive="both")]
    if frame.empty:
        return []

    pa = _last_pitch_per_pa(frame)
    rows: list[dict[str, Any]] = []
    for inning, group in frame.groupby("inning"):
        inning_pa = pa[pa["inning"] == inning] if not pa.empty else pa
        events = inning_pa["event"].fillna("").str.lower()
        desc = group["description"].fillna("").str.lower()
        swings = desc.isin(SWING_DESCRIPTIONS)
        whiffs = desc.isin(WHIFF_DESCRIPTIONS)
        bbe = inning_pa[inning_pa["event"].fillna("").str.lower().isin(IN_PLAY_EVENTS)]
        hard = _numeric(bbe.get("exit_velocity", pd.Series(dtype=float))) >= 95

        pa_count = int(len(inning_pa))
        hits = int(events.isin(HIT_EVENTS).sum())
        walks = int(events.isin(WALK_EVENTS).sum())
        strikeouts = int(events.isin(STRIKEOUT_EVENTS).sum())
        total_bases = int(
            events.map({"single": 1, "double": 2, "triple": 3, "home_run": 4}).fillna(0).sum()
        )
        rows.append({
            "inning": int(inning),
            "pitches": int(len(group)),
            "pa": pa_count,
            "avg": round(hits / max(pa_count - walks, 1), 3),
            "ops_proxy": round((hits + walks) / max(pa_count, 1) + total_bases / max(pa_count, 1), 3),
            "k_pct": round(100 * strikeouts / max(pa_count, 1), 1),
            "bb_pct": round(100 * walks / max(pa_count, 1), 1),
            "velo": round(float(_numeric(group["release_velocity"]).mean()), 1),
            "spin": round(float(_numeric(group["release_spin_rate"]).mean()), 0),
            "whiff_pct": round(100 * int(whiffs.sum()) / max(int(swings.sum()), 1), 1),
            "hard_hit_pct": round(100 * int(hard.sum()) / max(len(bbe), 1), 1),
            "xwoba": round(float(_numeric(inning_pa["expected_woba"]).mean()), 3),
        })
    return rows


def build_release_summary(pitches: pd.DataFrame) -> list[dict[str, Any]]:
    needed = {"pitch_type", "release_pos_x", "release_pos_z"}
    if pitches.empty or not needed.issubset(pitches.columns):
        return []
    frame = pitches.dropna(subset=["pitch_type", "release_pos_x", "release_pos_z"]).copy()
    if frame.empty:
        return []
    frame["release_pos_x"] = _numeric(frame["release_pos_x"])
    frame["release_pos_z"] = _numeric(frame["release_pos_z"])
    frame["release_extension"] = _numeric(frame.get("release_extension", pd.Series(index=frame.index)))
    rows = []
    for pitch_type, group in frame.groupby("pitch_type"):
        rows.append({
            "pitch_type": str(pitch_type),
            "count": int(len(group)),
            "x": round(float(group["release_pos_x"].mean()), 3),
            "z": round(float(group["release_pos_z"].mean()), 3),
            "x_sd": round(float(group["release_pos_x"].std(ddof=0)), 3),
            "z_sd": round(float(group["release_pos_z"].std(ddof=0)), 3),
            "extension": round(float(group["release_extension"].mean()), 2),
        })
    return sorted(rows, key=lambda row: row["count"], reverse=True)


def build_heatmap(
    pitches: pd.DataFrame,
    value: str = "frequency",
    bins_x: int = 9,
    bins_z: int = 9,
) -> dict[str, Any]:
    """Return a smoothed normalized heat-map grid in catcher's-view coordinates."""
    if pitches.empty or not {"plate_x", "plate_z"}.issubset(pitches.columns):
        return {"grid": [], "samples": 0, "metric": value}
    frame = pitches.copy()
    frame["plate_x"] = _numeric(frame["plate_x"])
    frame["plate_z"] = _numeric(frame["plate_z"])
    frame = frame[frame["plate_x"].between(-2.0, 2.0) & frame["plate_z"].between(0.5, 4.5)]
    if frame.empty:
        return {"grid": [], "samples": 0, "metric": value}

    weights: np.ndarray | None = None
    if value == "damage":
        event = frame.get("event", pd.Series(index=frame.index, dtype=str)).fillna("").str.lower()
        weights = event.map({"single": 1.0, "double": 2.0, "triple": 3.0, "home_run": 4.0}).fillna(0.0).to_numpy()
    elif value == "whiff":
        desc = frame.get("description", pd.Series(index=frame.index, dtype=str)).fillna("").str.lower()
        weights = desc.isin(WHIFF_DESCRIPTIONS).astype(float).to_numpy()

    hist, _, _ = np.histogram2d(
        frame["plate_z"].to_numpy(),
        frame["plate_x"].to_numpy(),
        bins=[bins_z, bins_x],
        range=[[0.5, 4.5], [-2.0, 2.0]],
        weights=weights,
    )
    # Lightweight 3x3 Gaussian-like smoothing without scipy.
    kernel = np.array([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=float)
    kernel /= kernel.sum()
    padded = np.pad(hist, 1, mode="edge")
    smooth = np.zeros_like(hist, dtype=float)
    for row in range(hist.shape[0]):
        for col in range(hist.shape[1]):
            smooth[row, col] = float(np.sum(padded[row:row + 3, col:col + 3] * kernel))
    maximum = float(np.nanmax(smooth)) if smooth.size else 0.0
    normalized = smooth / maximum if maximum > 0 else smooth
    return {
        "grid": np.flipud(normalized).round(4).tolist(),
        "raw_grid": np.flipud(smooth).round(3).tolist(),
        "samples": int(len(frame)),
        "metric": value,
        "x_min": -2.0,
        "x_max": 2.0,
        "z_min": 0.5,
        "z_max": 4.5,
    }


def build_team_rolling_offense(frame: pd.DataFrame, windows: Iterable[int] = (7, 15, 30)) -> dict[str, Any]:
    if frame.empty:
        return {"season": {}, "rolling": []}
    data = frame.copy()
    data["game_date"] = pd.to_datetime(data["game_date"], errors="coerce")
    pa = _last_pitch_per_pa(data)
    if pa.empty:
        return {"season": {}, "rolling": []}

    def summarize(part: pd.DataFrame) -> dict[str, Any]:
        events = part["event"].fillna("").str.lower()
        pa_count = len(part)
        ab = int((~events.isin(WALK_EVENTS | {"hit_by_pitch", "sac_fly", "sac_bunt", "catcher_interf"})).sum())
        hits = int(events.isin(HIT_EVENTS).sum())
        walks = int(events.isin(WALK_EVENTS).sum())
        hbp = int((events == "hit_by_pitch").sum())
        sf = int((events == "sac_fly").sum())
        tb = int(events.map({"single": 1, "double": 2, "triple": 3, "home_run": 4}).fillna(0).sum())
        strikeouts = int(events.isin(STRIKEOUT_EVENTS).sum())
        bbe = part[events.isin(IN_PLAY_EVENTS)]
        ev = _numeric(bbe.get("exit_velocity", pd.Series(dtype=float)))
        obp_den = ab + walks + hbp + sf
        return {
            "games": int(part["game_pk"].nunique()),
            "pa": int(pa_count),
            "avg": round(hits / max(ab, 1), 3),
            "obp": round((hits + walks + hbp) / max(obp_den, 1), 3),
            "slg": round(tb / max(ab, 1), 3),
            "ops": round((hits + walks + hbp) / max(obp_den, 1) + tb / max(ab, 1), 3),
            "k_pct": round(100 * strikeouts / max(pa_count, 1), 1),
            "bb_pct": round(100 * walks / max(pa_count, 1), 1),
            "hard_hit_pct": round(100 * int((ev >= 95).sum()) / max(int(ev.notna().sum()), 1), 1),
            "avg_ev": round(float(ev.mean()), 1),
            "xwoba": round(float(_numeric(part.get("expected_woba", pd.Series(dtype=float))).mean()), 3),
        }

    dates = sorted(pa["game_date"].dropna().dt.normalize().unique())
    rolling = []
    for window in windows:
        selected_dates = set(dates[-int(window):])
        part = pa[pa["game_date"].dt.normalize().isin(selected_dates)]
        values = summarize(part)
        values["window"] = f"Last {window} games"
        rolling.append(values)
    return {"season": summarize(pa), "rolling": rolling}
