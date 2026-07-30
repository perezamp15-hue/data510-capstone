"""Train and evaluate the next-pitch classification model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    log_loss,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sqlalchemy import select

from baseball_capstone.database.engine import session_scope
from baseball_capstone.database.models import PitchSequenceFeature


CATEGORICAL_FEATURES = [
    "pitcher_id",
    "batter_id",
    "pitcher_hand",
    "batter_side",
    "previous_pitch_type",
    "previous_pitch_zone",
    "previous_pitch_result",
    "second_previous_pitch_type",
    "second_previous_pitch_zone",
    "third_previous_pitch_type",
    "inning_half",
]

NUMERIC_FEATURES = [
    "balls_before_pitch",
    "strikes_before_pitch",
    "outs_before_pitch",
    "inning",
    "runner_on_first",
    "runner_on_second",
    "runner_on_third",
]

MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


@dataclass(frozen=True, slots=True)
class ModelEvaluation:
    """Evaluation metrics for one trained model."""

    training_rows: int
    test_rows: int
    top_one_accuracy: float
    top_three_accuracy: float
    macro_f1: float
    multiclass_log_loss: float


@dataclass(frozen=True, slots=True)
class TrainingResult:
    """Summary of a completed model-training run."""

    output_path: Path
    evaluation: ModelEvaluation
    classes: list[str]


def group_pitch_type(pitch_type: str | None) -> str:
    """Convert MLB pitch codes into broader model classes."""
    code = (pitch_type or "").strip().upper()

    pitch_groups = {
        "FF": "fastball",
        "FA": "fastball",
        "SI": "sinker",
        "FT": "sinker",
        "FC": "cutter",
        "SL": "slider",
        "ST": "slider",
        "SV": "slider",
        "CU": "curveball",
        "KC": "curveball",
        "CS": "curveball",
        "CH": "changeup",
        "FS": "splitter",
        "FO": "splitter",
    }

    return pitch_groups.get(code, "other")


def load_feature_dataframe(
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Load sequence features from PostgreSQL."""
    if end_date < start_date:
        raise ValueError("end_date cannot be before start_date.")

    with session_scope() as session:
        rows = session.execute(
            select(
                PitchSequenceFeature.game_date,
                PitchSequenceFeature.game_pk,
                PitchSequenceFeature.at_bat_number,
                PitchSequenceFeature.pitch_number,
                PitchSequenceFeature.pitcher_id,
                PitchSequenceFeature.batter_id,
                PitchSequenceFeature.pitcher_hand,
                PitchSequenceFeature.batter_side,
                PitchSequenceFeature.inning,
                PitchSequenceFeature.inning_half,
                PitchSequenceFeature.outs_before_pitch,
                PitchSequenceFeature.balls_before_pitch,
                PitchSequenceFeature.strikes_before_pitch,
                PitchSequenceFeature.previous_pitch_type,
                PitchSequenceFeature.previous_pitch_zone,
                PitchSequenceFeature.previous_pitch_result,
                PitchSequenceFeature.second_previous_pitch_type,
                PitchSequenceFeature.second_previous_pitch_zone,
                PitchSequenceFeature.third_previous_pitch_type,
                PitchSequenceFeature.runner_on_first,
                PitchSequenceFeature.runner_on_second,
                PitchSequenceFeature.runner_on_third,
                PitchSequenceFeature.target_pitch_type,
            )
            .where(
                PitchSequenceFeature.game_date.between(
                    start_date,
                    end_date,
                )
            )
            .order_by(
                PitchSequenceFeature.game_date,
                PitchSequenceFeature.game_pk,
                PitchSequenceFeature.at_bat_number,
                PitchSequenceFeature.pitch_number,
            )
        ).mappings().all()

    dataframe = pd.DataFrame(rows)

    if dataframe.empty:
        return dataframe

    dataframe["target_pitch_group"] = dataframe[
        "target_pitch_type"
    ].map(group_pitch_type)

    # Treat IDs as categories rather than continuous numbers.
    dataframe["pitcher_id"] = dataframe["pitcher_id"].astype(str)
    dataframe["batter_id"] = dataframe["batter_id"].astype(str)

    boolean_columns = [
        "runner_on_first",
        "runner_on_second",
        "runner_on_third",
    ]

    for column in boolean_columns:
        dataframe[column] = (
            dataframe[column]
            .fillna(False)
            .astype(int)
        )

    return dataframe


def build_model_pipeline() -> Pipeline:
    """Create the preprocessing and classifier pipeline."""
    categorical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="constant",
                    fill_value="missing",
                ),
            ),
            (
                "encoder",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                ),
            ),
        ]
    )

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
        ]
    )

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
        ],
        remainder="drop",
    )

    classifier = HistGradientBoostingClassifier(
        learning_rate=0.08,
        max_iter=250,
        max_leaf_nodes=31,
        min_samples_leaf=25,
        l2_regularization=1.0,
        random_state=42,
    )

    return Pipeline(
        steps=[
            ("preprocessing", preprocessing),
            ("classifier", classifier),
        ]
    )


def calculate_top_k_accuracy(
    actual: pd.Series,
    probabilities: np.ndarray,
    classes: np.ndarray,
    k: int,
) -> float:
    """Calculate multiclass top-k accuracy."""
    if len(actual) == 0:
        return 0.0

    number_of_classes = probabilities.shape[1]
    effective_k = min(k, number_of_classes)

    top_indices = np.argsort(
        probabilities,
        axis=1,
    )[:, -effective_k:]

    actual_values = actual.to_numpy()

    correct = 0

    for row_index, class_indices in enumerate(top_indices):
        predicted_classes = classes[class_indices]

        if actual_values[row_index] in predicted_classes:
            correct += 1

    return correct / len(actual_values)


def train_next_pitch_model(
    *,
    training_start_date: date,
    training_end_date: date,
    test_start_date: date,
    test_end_date: date,
    output_path: Path,
) -> TrainingResult:
    """Train, evaluate, and save the next-pitch model."""
    if training_end_date >= test_start_date:
        raise ValueError(
            "Training must end before the test period begins."
        )

    training_data = load_feature_dataframe(
        training_start_date,
        training_end_date,
    )

    test_data = load_feature_dataframe(
        test_start_date,
        test_end_date,
    )

    if training_data.empty:
        raise RuntimeError(
            "No pitch-sequence training rows were found."
        )

    if test_data.empty:
        raise RuntimeError(
            "No pitch-sequence test rows were found."
        )

    training_data = training_data.dropna(
        subset=["target_pitch_group"]
    )

    test_data = test_data.dropna(
        subset=["target_pitch_group"]
    )

    x_train = training_data[MODEL_FEATURES]
    y_train = training_data["target_pitch_group"]

    x_test = test_data[MODEL_FEATURES]
    y_test = test_data["target_pitch_group"]

    model = build_model_pipeline()
    model.fit(x_train, y_train)

    predicted_classes = model.predict(x_test)
    probabilities = model.predict_proba(x_test)

    classifier = model.named_steps["classifier"]
    classes = np.asarray(classifier.classes_)

    evaluation = ModelEvaluation(
        training_rows=len(training_data),
        test_rows=len(test_data),
        top_one_accuracy=accuracy_score(
            y_test,
            predicted_classes,
        ),
        top_three_accuracy=calculate_top_k_accuracy(
            actual=y_test,
            probabilities=probabilities,
            classes=classes,
            k=3,
        ),
        macro_f1=f1_score(
            y_test,
            predicted_classes,
            average="macro",
            zero_division=0,
        ),
        multiclass_log_loss=log_loss(
            y_test,
            probabilities,
            labels=classes,
        ),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    artifact: dict[str, Any] = {
        "model": model,
        "model_type": "HistGradientBoostingClassifier",
        "feature_columns": MODEL_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "classes": classes.tolist(),
        "training_start_date": training_start_date.isoformat(),
        "training_end_date": training_end_date.isoformat(),
        "test_start_date": test_start_date.isoformat(),
        "test_end_date": test_end_date.isoformat(),
        "evaluation": {
            "training_rows": evaluation.training_rows,
            "test_rows": evaluation.test_rows,
            "top_one_accuracy": evaluation.top_one_accuracy,
            "top_three_accuracy": evaluation.top_three_accuracy,
            "macro_f1": evaluation.macro_f1,
            "multiclass_log_loss": (
                evaluation.multiclass_log_loss
            ),
        },
    }

    joblib.dump(artifact, output_path)

    return TrainingResult(
        output_path=output_path,
        evaluation=evaluation,
        classes=classes.tolist(),
    )