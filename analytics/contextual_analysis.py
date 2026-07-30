from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


def _num(frame: pd.DataFrame, col: str, default: float = np.nan) -> pd.Series:
    if col not in frame:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[col], errors="coerce")


def _rate(mask: pd.Series, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(mask.fillna(False).sum()) / denominator * 100, 1)


def _is_whiff(frame: pd.DataFrame) -> pd.Series:
    desc = frame.get("pitch_description", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    return desc.str.contains("swinging_strike|swinging strike|foul_tip|foul tip", regex=True)


def _is_swing(frame: pd.DataFrame) -> pd.Series:
    desc = frame.get("pitch_description", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    return desc.str.contains("swing|foul|hit_into_play|in play", regex=True)


def _is_strike(frame: pd.DataFrame) -> pd.Series:
    desc = frame.get("pitch_description", pd.Series("", index=frame.index)).fillna("").astype(str).str.lower()
    return desc.str.contains("strike|foul|hit_into_play|in play", regex=True)


def summarize_sample(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"pitches": 0, "games": 0}
    swings = _is_swing(frame)
    whiffs = _is_whiff(frame)
    ev = _num(frame, "exit_velocity")
    xwoba = _num(frame, "expected_woba")
    velo = _num(frame, "release_velocity")
    hard = frame.get("database_is_hard_hit", ev.ge(95)).fillna(False).astype(bool)
    return {
        "pitches": int(len(frame)),
        "games": int(frame.get("game_pk", pd.Series(dtype=float)).nunique()),
        "velocity": round(float(velo.mean()), 1) if velo.notna().any() else None,
        "strike_rate": _rate(_is_strike(frame), len(frame)),
        "swing_rate": _rate(swings, len(frame)),
        "whiff_rate": _rate(whiffs & swings, int(swings.sum())),
        "hard_hit_rate": _rate(hard, int(ev.notna().sum())),
        "avg_exit_velocity": round(float(ev.mean()), 1) if ev.notna().any() else None,
        "xwoba": round(float(xwoba.mean()), 3) if xwoba.notna().any() else None,
    }


def recent_games(frame: pd.DataFrame, games: int = 5) -> dict[str, Any]:
    if frame.empty or "game_pk" not in frame:
        return {"label": f"Last {games} games", "summary": summarize_sample(pd.DataFrame()), "game_ids": []}
    work = frame.copy()
    work["game_date"] = pd.to_datetime(work.get("game_date"), errors="coerce")
    game_order = (work.groupby("game_pk", dropna=True)["game_date"].max().sort_values(ascending=False).head(games))
    selected = work[work["game_pk"].isin(game_order.index)]
    return {"label": f"Last {games} games", "summary": summarize_sample(selected), "game_ids": [int(x) for x in game_order.index]}


def _split_row(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    return {"label": label, **summarize_sample(frame)}


def home_away_splits(frame: pd.DataFrame, pitcher_team_id: int | None = None) -> list[dict[str, Any]]:
    if frame.empty or pitcher_team_id is None or "home_team_id" not in frame:
        return []
    home = _num(frame, "home_team_id").eq(int(pitcher_team_id))
    away = _num(frame, "away_team_id").eq(int(pitcher_team_id))
    return [_split_row("Home", frame[home]), _split_row("Away", frame[away])]


def game_state_splits(frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if frame.empty:
        return {"runners": [], "innings": [], "times_through_order": []}
    r1 = frame.get("runner_on_first", False)
    r2 = frame.get("runner_on_second", False)
    r3 = frame.get("runner_on_third", False)
    r1 = pd.Series(r1, index=frame.index).fillna(False).astype(bool)
    r2 = pd.Series(r2, index=frame.index).fillna(False).astype(bool)
    r3 = pd.Series(r3, index=frame.index).fillna(False).astype(bool)
    inning = _num(frame, "inning", 1)
    runners = [
        _split_row("Bases empty", frame[~(r1 | r2 | r3)]),
        _split_row("Runner on first only", frame[r1 & ~r2 & ~r3]),
        _split_row("Runner in scoring position", frame[r2 | r3]),
        _split_row("Bases loaded", frame[r1 & r2 & r3]),
    ]
    innings = [
        _split_row("Early (1-3)", frame[inning.le(3)]),
        _split_row("Middle (4-6)", frame[inning.between(4, 6)]),
        _split_row("Late (7+)", frame[inning.ge(7)]),
    ]
    if "at_bat_number" in frame and "game_pk" in frame:
        pa = frame[["game_pk", "batter_id", "at_bat_number"]].drop_duplicates().sort_values(["game_pk", "batter_id", "at_bat_number"])
        pa["tto"] = pa.groupby(["game_pk", "batter_id"]).cumcount() + 1
        work = frame.merge(pa, on=["game_pk", "batter_id", "at_bat_number"], how="left")
        tto = [
            _split_row("First look", work[work["tto"].eq(1)]),
            _split_row("Second look", work[work["tto"].eq(2)]),
            _split_row("Third+ look", work[work["tto"].ge(3)]),
        ]
    else:
        tto = []
    return {"runners": runners, "innings": innings, "times_through_order": tto}


def pitcher_self_comparison(frame: pd.DataFrame, games: int = 5) -> list[dict[str, Any]]:
    season = summarize_sample(frame)
    recent = recent_games(frame, games)["summary"]
    metrics = [
        ("Velocity", "velocity", "mph"), ("Strike rate", "strike_rate", "%"),
        ("Whiff rate", "whiff_rate", "%"), ("Hard-hit rate", "hard_hit_rate", "%"),
        ("xwOBA", "xwoba", ""),
    ]
    rows = []
    for label, key, suffix in metrics:
        a, b = season.get(key), recent.get(key)
        delta = round(b - a, 3 if key == "xwoba" else 1) if a is not None and b is not None else None
        rows.append({"metric": label, "season": a, "recent": b, "delta": delta, "suffix": suffix})
    return rows


def percentile_rank(value: float | None, population: pd.Series, higher_is_better: bool = True) -> float | None:
    clean = pd.to_numeric(population, errors="coerce").dropna()
    if value is None or clean.empty:
        return None
    pct = float((clean.le(value).mean() if higher_is_better else clean.ge(value).mean()) * 100)
    return round(pct, 0)


def build_pitcher_comparables(target: pd.DataFrame, league: pd.DataFrame, limit: int = 5) -> dict[str, Any]:
    if target.empty or league.empty or "pitcher_id" not in league:
        return {"similar": [], "rankings": []}
    def profiles(df: pd.DataFrame) -> pd.DataFrame:
        rows=[]
        for pid,g in df.groupby("pitcher_id"):
            s=summarize_sample(g)
            usage=g["pitch_type"].value_counts(normalize=True) if "pitch_type" in g else pd.Series(dtype=float)
            rows.append({"pitcher_id":int(pid),"pitcher_name":str(g.get("pitcher_name",pd.Series([pid])).iloc[0]),
                         "velocity":s.get("velocity"),"whiff_rate":s.get("whiff_rate"),"strike_rate":s.get("strike_rate"),
                         "xwoba":s.get("xwoba"),"ff_usage":float(usage.get("FF",0)*100),"sl_usage":float(usage.get("SL",0)*100),
                         "ch_usage":float(usage.get("CH",0)*100),"si_usage":float(usage.get("SI",0)*100),"pitches":len(g)})
        return pd.DataFrame(rows)
    pop=profiles(league)
    target_id=int(target["pitcher_id"].dropna().iloc[0])
    if target_id not in pop["pitcher_id"].values:
        pop=pd.concat([pop,profiles(target)],ignore_index=True)
    features=["velocity","whiff_rate","strike_rate","xwoba","ff_usage","sl_usage","ch_usage","si_usage"]
    X=pop[features].apply(pd.to_numeric,errors="coerce")
    X=X.fillna(X.median(numeric_only=True)).fillna(0)
    std=X.std(ddof=0).replace(0,1)
    z=(X-X.mean())/std
    idx=pop.index[pop["pitcher_id"].eq(target_id)]
    if len(idx)==0:return {"similar":[],"rankings":[]}
    distances=np.sqrt(((z-z.loc[idx[0]])**2).sum(axis=1))
    similar=pop.assign(distance=distances).loc[lambda d: d.pitcher_id.ne(target_id)].sort_values("distance").head(limit)
    t=pop.loc[idx[0]]
    rankings=[
        {"metric":"Velocity","value":t.velocity,"percentile":percentile_rank(t.velocity,pop.velocity,True)},
        {"metric":"Whiff rate","value":t.whiff_rate,"percentile":percentile_rank(t.whiff_rate,pop.whiff_rate,True)},
        {"metric":"Strike rate","value":t.strike_rate,"percentile":percentile_rank(t.strike_rate,pop.strike_rate,True)},
        {"metric":"Contact suppression (xwOBA)","value":t.xwoba,"percentile":percentile_rank(t.xwoba,pop.xwoba,False)},
    ]
    return {"similar":similar[["pitcher_id","pitcher_name","velocity","whiff_rate","strike_rate","xwoba","distance"]].round(3).to_dict("records"),"rankings":rankings}


def bullpen_summary(frame: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if frame.empty or "pitcher_id" not in frame:
        return []
    work=frame.copy(); work["game_date"]=pd.to_datetime(work.get("game_date"),errors="coerce")
    rows=[]
    for pid,g in work.groupby("pitcher_id"):
        s=summarize_sample(g)
        recent_dates=g["game_date"].dropna().dt.date.nunique()
        rows.append({"pitcher_id":int(pid),"pitcher_name":str(g.get("pitcher_name",pd.Series([pid])).iloc[0]),
                     "throws":str(g.get("throws",pd.Series([""])).iloc[0] or ""),"appearances":int(recent_dates),
                     "pitches":s.get("pitches"),"velocity":s.get("velocity"),"whiff_rate":s.get("whiff_rate"),"xwoba":s.get("xwoba")})
    return sorted(rows,key=lambda x:(x["appearances"],x["pitches"]),reverse=True)[:limit]
