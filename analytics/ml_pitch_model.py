"""Optional machine-learning models for pitch tendency and sequence support.

The model predicts the probability of each pitch type from pre-pitch information.
It is not a Monte Carlo simulation and it does not invent future game outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
except ImportError:  # pragma: no cover
    ColumnTransformer = HistGradientBoostingClassifier = SimpleImputer = Pipeline = OneHotEncoder = None


NUMERIC_FEATURES = [
    "ball_count", "strike_count", "outs", "inning", "pitch_number",
    "runner_on_first", "runner_on_second", "runner_on_third",
    "score_diff",
]
CATEGORICAL_FEATURES = ["batter_side", "previous_pitch_type", "previous_result"]


@dataclass
class PitchModelResult:
    available: bool
    sample_size: int
    classes: list[str]
    accuracy: float | None
    baseline_accuracy: float | None
    top2_accuracy: float | None
    note: str
    model: Any = None


def _text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str)


def prepare_training_data(pitches: pd.DataFrame) -> pd.DataFrame:
    if pitches.empty:
        return pd.DataFrame()
    data = pitches.copy()
    sort_cols = [c for c in ["game_date", "game_pk", "at_bat_number", "pitch_number"] if c in data]
    if sort_cols:
        data = data.sort_values(sort_cols)
    pa_keys = [c for c in ["game_pk", "at_bat_number"] if c in data]
    if len(pa_keys) < 2:
        pa_keys = [c for c in ["game_pk", "plate_appearance_number"] if c in data]
    if pa_keys:
        data["previous_pitch_type"] = data.groupby(pa_keys)["pitch_type"].shift(1)
        result_col = "pitch_description" if "pitch_description" in data else "events"
        data["previous_result"] = data.groupby(pa_keys)[result_col].shift(1)
    else:
        data["previous_pitch_type"] = "START"
        data["previous_result"] = "START"

    data["previous_pitch_type"] = _text(data["previous_pitch_type"]).replace("", "START")
    data["previous_result"] = _text(data["previous_result"]).replace("", "START")
    data["batter_side"] = _text(data.get("batter_side", pd.Series(index=data.index, dtype=str))).replace("", "U")
    for col in ["runner_on_first", "runner_on_second", "runner_on_third"]:
        data[col] = data.get(col, False).fillna(False).astype(int)
    home = pd.to_numeric(data.get("home_score", 0), errors="coerce").fillna(0)
    away = pd.to_numeric(data.get("away_score", 0), errors="coerce").fillna(0)
    half = _text(data.get("inning_half", pd.Series(index=data.index, dtype=str))).str.lower()
    data["score_diff"] = np.where(half.eq("top"), away - home, home - away)
    for col in ["ball_count", "strike_count", "outs", "inning", "pitch_number"]:
        data[col] = pd.to_numeric(data.get(col, 0), errors="coerce")
    return data.loc[data["pitch_type"].notna()].copy()


def train_pitch_model(pitches: pd.DataFrame, minimum_rows: int = 250) -> PitchModelResult:
    if Pipeline is None:
        return PitchModelResult(False, 0, [], None, None, None, "Install scikit-learn to enable machine learning.")
    data = prepare_training_data(pitches)
    if len(data) < minimum_rows or data["pitch_type"].nunique() < 2:
        return PitchModelResult(False, len(data), sorted(data.get("pitch_type", pd.Series(dtype=str)).dropna().unique().tolist()), None, None, None,
                                f"Need at least {minimum_rows} pitches and two pitch types for ML.")

    # Time-ordered holdout avoids leaking later pitches into evaluation.
    split = max(int(len(data) * 0.80), 1)
    train, test = data.iloc[:split], data.iloc[split:]
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median"))]), NUMERIC_FEATURES),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), CATEGORICAL_FEATURES),
    ])
    model = Pipeline([
        ("features", pre),
        ("classifier", HistGradientBoostingClassifier(max_iter=160, learning_rate=0.07, max_leaf_nodes=24,
                                                       l2_regularization=1.0, random_state=42)),
    ])
    model.fit(train[NUMERIC_FEATURES + CATEGORICAL_FEATURES], train["pitch_type"].astype(str))
    accuracy = float(model.score(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES], test["pitch_type"].astype(str))) if len(test) else None
    classes = list(model.named_steps["classifier"].classes_)
    baseline = None
    top2 = None
    if len(test):
        y_test = test["pitch_type"].astype(str).to_numpy()
        most_common = train["pitch_type"].astype(str).mode().iloc[0]
        baseline = float(np.mean(y_test == most_common))
        probabilities = model.predict_proba(test[NUMERIC_FEATURES + CATEGORICAL_FEATURES])
        top_indices = np.argsort(probabilities, axis=1)[:, -2:]
        class_array = np.asarray(classes)
        top2 = float(np.mean([actual in class_array[indexes] for actual, indexes in zip(y_test, top_indices)]))
    return PitchModelResult(True, len(data), classes,
                            round(accuracy, 3) if accuracy is not None else None,
                            round(baseline, 3) if baseline is not None else None,
                            round(top2, 3) if top2 is not None else None,
                            "Gradient-boosted classifier trained on time-ordered historical pitches.", model)


def predict_pitch_probabilities(result: PitchModelResult, *, balls: int, strikes: int,
                                batter_side: str, previous_pitch_type: str = "START",
                                previous_result: str = "START", outs: int = 0,
                                inning: int = 1, pitch_number: int = 1,
                                runners: tuple[int, int, int] = (0, 0, 0), score_diff: int = 0) -> dict[str, float]:
    if not result.available or result.model is None:
        return {}
    row = pd.DataFrame([{
        "ball_count": balls, "strike_count": strikes, "outs": outs, "inning": inning,
        "pitch_number": pitch_number, "runner_on_first": runners[0], "runner_on_second": runners[1],
        "runner_on_third": runners[2], "score_diff": score_diff,
        "batter_side": (batter_side or "U").upper(),
        "previous_pitch_type": previous_pitch_type or "START",
        "previous_result": previous_result or "START",
    }])
    probabilities = result.model.predict_proba(row[NUMERIC_FEATURES + CATEGORICAL_FEATURES])[0]
    return {str(code): round(float(prob) * 100, 1) for code, prob in sorted(zip(result.classes, probabilities), key=lambda x: x[1], reverse=True)}


def count_tendencies(result: PitchModelResult, batter_side: str) -> list[dict[str, Any]]:
    situations = [(0, 0, "First pitch"), (0, 1, "Ahead 0-1"), (1, 0, "Behind 1-0"),
                  (1, 2, "Put-away 1-2"), (2, 2, "Even 2-2"), (3, 2, "Full count")]
    rows = []
    for balls, strikes, label in situations:
        probs = predict_pitch_probabilities(result, balls=balls, strikes=strikes, batter_side=batter_side)
        rows.append({"label": label, "balls": balls, "strikes": strikes, "probabilities": probs,
                     "top_pitch": next(iter(probs), ""), "top_probability": next(iter(probs.values()), None)})
    return rows
