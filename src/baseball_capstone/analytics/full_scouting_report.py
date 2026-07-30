"""Build a complete two-team pitcher and lineup scouting report.

The report combines PostgreSQL pitch history with the trained deterministic ML
bundle. Traditional values derived from pitch-by-pitch data are explicitly
labelled as estimates when official box-score earned-run data is unavailable.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select

from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import Pitch, Player
from baseball_capstone.models.final_strategy import FinalStrategyBundle, PITCH_NAMES, ZONE_NAMES

WHIFFS = {"swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"}
SWINGS = WHIFFS | {"foul", "foul_bunt", "hit_into_play"}
WALKS = {"walk", "intent_walk", "intentional_walk"}
STRIKEOUTS = {"strikeout", "strikeout_double_play"}
HITS = {"single", "double", "triple", "home_run"}


@dataclass(slots=True)
class PlayerInfo:
    player_id: int
    name: str
    bats: str | None
    throws: str | None
    position: str | None


def _f(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return default if np.isnan(result) else result
    except (TypeError, ValueError):
        return default


def player_info(player_id: int) -> PlayerInfo:
    with session_scope() as session:
        row = session.get(Player, player_id)
        if row is None:
            raise ValueError(f"Player ID {player_id} was not found in the players table.")
        return PlayerInfo(row.player_id, row.full_name, row.bats, row.throws, row.primary_position)


def _pitch_frame(*, pitcher_id: int | None = None, batter_id: int | None = None,
                 start_date: date, end_date: date) -> pd.DataFrame:
    columns = [
        Pitch.pitch_id, Pitch.game_pk, Pitch.game_date, Pitch.at_bat_number,
        Pitch.pitch_number, Pitch.inning, Pitch.outs, Pitch.balls, Pitch.strikes,
        Pitch.pitcher_id, Pitch.batter_id, Pitch.pitch_type, Pitch.description,
        Pitch.event_type, Pitch.is_ball, Pitch.is_strike, Pitch.is_in_play,
        Pitch.release_speed, Pitch.release_spin_rate, Pitch.release_extension,
        Pitch.release_pos_x, Pitch.release_pos_z, Pitch.plate_x, Pitch.plate_z,
        Pitch.pfx_x, Pitch.pfx_z, Pitch.launch_speed, Pitch.launch_angle,
        Pitch.estimated_batting_average, Pitch.estimated_woba,
        Pitch.estimated_slugging, Pitch.zone,
    ]
    statement = select(*columns).where(Pitch.game_date.between(start_date, end_date))
    if pitcher_id is not None:
        statement = statement.where(Pitch.pitcher_id == pitcher_id)
    if batter_id is not None:
        statement = statement.where(Pitch.batter_id == batter_id)
    with session_scope() as session:
        rows = session.execute(statement).mappings().all()
    return pd.DataFrame(rows)


def pitcher_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"pitch_count": 0, "warning": "No pitch history in the selected date range."}
    data = frame.copy()
    desc = data["description"].fillna("").astype(str)
    terminal = data.sort_values(["game_pk", "at_bat_number", "pitch_number"]).groupby(
        ["game_pk", "at_bat_number"], as_index=False
    ).tail(1)
    events = terminal["event_type"].fillna("").astype(str)
    pa = len(terminal)
    hits = int(events.isin(HITS).sum())
    walks = int(events.isin(WALKS).sum())
    strikeouts = int(events.isin(STRIKEOUTS).sum())
    # Pitch feed has outs before a pitch rather than official pitching outs.
    # Estimate innings from PA outcomes that normally record an out.
    non_outcomes = HITS | WALKS | {"hit_by_pitch", "catcher_interf"}
    outs_est = int((~events.isin(non_outcomes) & events.ne("")).sum())
    innings_est = outs_est / 3.0
    swings = desc.isin(SWINGS)
    whiffs = desc.isin(WHIFFS)
    in_zone = data["zone"].between(1, 9, inclusive="both")
    contact = swings & ~whiffs
    hard = pd.to_numeric(data["launch_speed"], errors="coerce").ge(95)
    bip = data["is_in_play"].fillna(False).astype(bool)
    return {
        "pitch_count": int(len(data)),
        "games": int(data["game_pk"].nunique()),
        "plate_appearances": int(pa),
        "innings_est": innings_est,
        "hits_allowed": hits,
        "walks": walks,
        "strikeouts": strikeouts,
        "whip_est": (hits + walks) / innings_est if innings_est else None,
        "k_rate": strikeouts / pa if pa else 0.0,
        "bb_rate": walks / pa if pa else 0.0,
        "strike_rate": data["is_strike"].fillna(False).mean(),
        "first_pitch_strike_rate": data[data["pitch_number"] == 1]["is_strike"].fillna(False).mean(),
        "whiff_rate": whiffs.sum() / swings.sum() if swings.sum() else 0.0,
        "swinging_strike_rate": whiffs.mean(),
        "zone_rate": in_zone.mean(),
        "contact_rate": contact.sum() / swings.sum() if swings.sum() else 0.0,
        "hard_hit_rate": hard[bip].mean() if bip.sum() else 0.0,
        "avg_exit_velocity": pd.to_numeric(data.loc[bip, "launch_speed"], errors="coerce").mean(),
        "xwoba": pd.to_numeric(data["estimated_woba"], errors="coerce").mean(),
        "xba": pd.to_numeric(data["estimated_batting_average"], errors="coerce").mean(),
        "xslg": pd.to_numeric(data["estimated_slugging"], errors="coerce").mean(),
        "warning": "WHIP and innings are pitch-feed estimates; official ERA is not available from the current schema.",
    }


def arsenal_summary(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    total = len(frame[frame["pitch_type"].notna()])
    rows: list[dict[str, Any]] = []
    for code, group in frame.dropna(subset=["pitch_type"]).groupby("pitch_type"):
        desc = group["description"].fillna("").astype(str)
        swings = desc.isin(SWINGS)
        whiffs = desc.isin(WHIFFS)
        bip = group["is_in_play"].fillna(False).astype(bool)
        rows.append({
            "code": str(code), "name": PITCH_NAMES.get(str(code), str(code)),
            "count": len(group), "usage": len(group) / total if total else 0.0,
            "velocity": pd.to_numeric(group["release_speed"], errors="coerce").mean(),
            "spin": pd.to_numeric(group["release_spin_rate"], errors="coerce").mean(),
            "extension": pd.to_numeric(group["release_extension"], errors="coerce").mean(),
            "strike_rate": group["is_strike"].fillna(False).mean(),
            "whiff_rate": whiffs.sum() / swings.sum() if swings.sum() else 0.0,
            "zone_rate": group["zone"].between(1, 9, inclusive="both").mean(),
            "hard_hit_rate": pd.to_numeric(group.loc[bip, "launch_speed"], errors="coerce").ge(95).mean() if bip.sum() else 0.0,
            "xwoba": pd.to_numeric(group["estimated_woba"], errors="coerce").mean(),
            "pfx_x": pd.to_numeric(group["pfx_x"], errors="coerce").mean(),
            "pfx_z": pd.to_numeric(group["pfx_z"], errors="coerce").mean(),
            "release_x": pd.to_numeric(group["release_pos_x"], errors="coerce").mean(),
            "release_z": pd.to_numeric(group["release_pos_z"], errors="coerce").mean(),
        })
    return sorted(rows, key=lambda item: item["count"], reverse=True)


def batter_weakness(frame: pd.DataFrame, pitcher_arsenal: list[dict[str, Any]]) -> dict[str, Any]:
    if frame.empty:
        return {"pitch_count": 0, "pitch_splits": [], "zone_cells": [], "summary": "No batter history available."}
    arsenal_codes = {item["code"] for item in pitcher_arsenal}
    available = frame[frame["pitch_type"].isin(arsenal_codes)] if arsenal_codes else frame
    splits = []
    for code, group in available.dropna(subset=["pitch_type"]).groupby("pitch_type"):
        desc = group["description"].fillna("").astype(str)
        swings = desc.isin(SWINGS); whiffs = desc.isin(WHIFFS)
        bip = group["is_in_play"].fillna(False).astype(bool)
        splits.append({
            "code": str(code), "name": PITCH_NAMES.get(str(code), str(code)), "count": len(group),
            "whiff_rate": whiffs.sum() / swings.sum() if swings.sum() else 0.0,
            "strike_rate": group["is_strike"].fillna(False).mean(),
            "in_play_rate": bip.mean(),
            "avg_exit_velocity": pd.to_numeric(group.loc[bip, "launch_speed"], errors="coerce").mean(),
            "xwoba": pd.to_numeric(group["estimated_woba"], errors="coerce").mean(),
        })
    splits.sort(key=lambda item: (item["whiff_rate"], -_f(item["xwoba"], .320)), reverse=True)
    zone_data = available.dropna(subset=["plate_x", "plate_z"]).copy()
    zone_data["x_bin"] = pd.cut(pd.to_numeric(zone_data["plate_x"], errors="coerce"), [-3, -.9, -.3, .3, .9, 3], labels=False)
    zone_data["z_bin"] = pd.cut(pd.to_numeric(zone_data["plate_z"], errors="coerce"), [0, 1.5, 2.15, 2.85, 3.5, 5], labels=False)
    cells = []
    for (x_bin, z_bin), group in zone_data.dropna(subset=["x_bin", "z_bin"]).groupby(["x_bin", "z_bin"]):
        desc = group["description"].fillna("").astype(str); swings = desc.isin(SWINGS)
        cells.append({"x": int(x_bin), "z": int(z_bin), "count": len(group),
                      "whiff_rate": desc.isin(WHIFFS).sum() / swings.sum() if swings.sum() else 0.0,
                      "xwoba": _f(pd.to_numeric(group["estimated_woba"], errors="coerce").mean(), .320)})
    qualified = [item for item in cells if item["count"] >= 5]
    struggle = max(qualified, key=lambda item: item["whiff_rate"] + max(.320-item["xwoba"], 0), default=None)
    hot = max(qualified, key=lambda item: item["xwoba"], default=None)
    zone_names = {(0,0):"low far inside",(1,0):"low inside",(2,0):"low middle",(3,0):"low away",(4,0):"low far away",
                  (0,1):"lower far inside",(1,1):"lower inside",(2,1):"lower middle",(3,1):"lower away",(4,1):"lower far away",
                  (0,2):"middle far inside",(1,2):"middle inside",(2,2):"middle",(3,2):"middle away",(4,2):"middle far away",
                  (0,3):"upper far inside",(1,3):"upper inside",(2,3):"upper middle",(3,3):"upper away",(4,3):"upper far away",
                  (0,4):"high far inside",(1,4):"high inside",(2,4):"high middle",(3,4):"high away",(4,4):"high far away"}
    weakest_pitch = splits[0] if splits else None
    summary = "Insufficient sample to identify a stable weakness."
    if weakest_pitch:
        summary = f"Most vulnerable against {weakest_pitch['name']} ({weakest_pitch['whiff_rate']:.1%} whiff rate"
        if struggle: summary += f") around {zone_names.get((struggle['x'], struggle['z']), 'the selected zone')}"
        else: summary += ")"
        summary += "."
    return {"pitch_count": len(frame), "pitch_splits": splits, "zone_cells": cells,
            "struggle_zone": zone_names.get((struggle["x"], struggle["z"])) if struggle else None,
            "hot_zone": zone_names.get((hot["x"], hot["z"])) if hot else None,
            "summary": summary}


def model_matchup(bundle: FinalStrategyBundle, features: pd.DataFrame, *, pitcher_id: int,
                  batter_id: int, balls: int = 0, strikes: int = 0) -> dict[str, Any]:
    subset = features[(features["pitcher_id"] == pitcher_id) & (features["batter_id"] == batter_id)].copy()
    ball_col = "balls" if "balls" in subset.columns else "ball_count"
    strike_col = "strikes" if "strikes" in subset.columns else "strike_count"
    exact = subset[(subset[ball_col] == balls) & (subset[strike_col] == strikes)] if ball_col in subset and strike_col in subset else subset
    context = exact if not exact.empty else subset
    if context.empty:
        return {"available": False, "warning": "No matching ML feature context."}
    if "game_date" in context:
        context["game_date"] = pd.to_datetime(context["game_date"], errors="coerce")
        context = context.sort_values("game_date")
    result = bundle.predict_context(context.tail(1), top_n=5)
    result["available"] = True
    result["context_rows"] = int(len(subset))
    return result


def build_pitcher_block(*, pitcher: PlayerInfo, opponent_lineup: list[PlayerInfo], start_date: date,
                        end_date: date, bundle: FinalStrategyBundle, features: pd.DataFrame) -> dict[str, Any]:
    pframe = _pitch_frame(pitcher_id=pitcher.player_id, start_date=start_date, end_date=end_date)
    arsenal = arsenal_summary(pframe)
    hitters = []
    for order, batter in enumerate(opponent_lineup, 1):
        bframe = _pitch_frame(batter_id=batter.player_id, start_date=start_date, end_date=end_date)
        weakness = batter_weakness(bframe, arsenal)
        ml = model_matchup(bundle, features, pitcher_id=pitcher.player_id, batter_id=batter.player_id)
        hitters.append({"order": order, "player": asdict(batter), "weakness": weakness, "ml": ml})
    return {"pitcher": asdict(pitcher), "summary": pitcher_summary(pframe), "arsenal": arsenal, "hitters": hitters}


def build_full_report(*, our_team: str, opponent_team: str, our_pitcher_id: int,
                      opposing_pitcher_id: int, our_lineup_ids: list[int], opponent_lineup_ids: list[int],
                      start_date: date, end_date: date, bundle: FinalStrategyBundle,
                      features: pd.DataFrame) -> dict[str, Any]:
    our_pitcher = player_info(our_pitcher_id); opposing_pitcher = player_info(opposing_pitcher_id)
    our_lineup = [player_info(value) for value in our_lineup_ids]
    opponent_lineup = [player_info(value) for value in opponent_lineup_ids]
    return {
        "our_team": our_team, "opponent_team": opponent_team,
        "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        "offense": build_pitcher_block(pitcher=opposing_pitcher, opponent_lineup=our_lineup,
                                       start_date=start_date, end_date=end_date, bundle=bundle, features=features),
        "defense": build_pitcher_block(pitcher=our_pitcher, opponent_lineup=opponent_lineup,
                                       start_date=start_date, end_date=end_date, bundle=bundle, features=features),
        "model_metrics": bundle.metadata.get("metrics", {}),
    }
