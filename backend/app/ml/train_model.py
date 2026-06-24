from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from app.agents.amount_anomaly_agent import AmountAnomalyAgent
from app.agents.duplicate_payment_agent import DuplicatePaymentAgent
from app.agents.location_risk_agent import LocationRiskAgent
from app.agents.merchant_risk_agent import MerchantRiskAgent
from app.agents.user_behavior_agent import UserBehaviorAgent
from app.agents.velocity_fraud_agent import VelocityFraudAgent
from app.core.cleaning import clean_transactions_dataframe
from app.core.schema_mapping import map_transaction_schema
from app.core.scoring import final_score_dataframe
from app.core.validation import validate_transaction_dataset
from app.ml.feature_engineering import build_ml_features

MODEL_DIR = Path(__file__).resolve().parent / "model_store"
MODEL_PATH = MODEL_DIR / "fraud_model.joblib"
METADATA_PATH = MODEL_DIR / "fraud_model_metadata.json"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DATA_DIR = PROJECT_ROOT / "sample_data"


def _read_dataset(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path, encoding="utf-8-sig", on_bad_lines="skip")


def _default_sample_paths() -> list[Path]:
    candidates = [
        SAMPLE_DATA_DIR / "standard_transactions.csv",
        SAMPLE_DATA_DIR / "messy_transactions.csv",
        SAMPLE_DATA_DIR / "edge_case_transactions.csv",
    ]
    return [path for path in candidates if path.exists()]


def _load_training_dataframe(input_path: str | None) -> pd.DataFrame:
    if input_path:
        path = Path(input_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Training input file not found: {path}")
        return _read_dataset(path)

    sample_paths = _default_sample_paths()
    if not sample_paths:
        raise FileNotFoundError("No input CSV was provided and sample_data CSV files were not found.")
    frames = [_read_dataset(path) for path in sample_paths]
    return pd.concat(frames, ignore_index=True)


def _score_with_existing_rules(raw_dataframe: pd.DataFrame) -> pd.DataFrame:
    mapping_result = map_transaction_schema(raw_dataframe)
    cleaning_result = clean_transactions_dataframe(mapping_result.dataframe)
    validation_report = validate_transaction_dataset(
        cleaning_result.dataframe,
        original_rows=len(raw_dataframe.index),
        original_columns=mapping_result.original_columns,
        mapped_columns=mapping_result.mapped_columns,
        missing_required_columns=mapping_result.missing_required_columns,
        cleaning_warnings=[*mapping_result.warnings, *cleaning_result.warnings],
    )
    if not validation_report.is_valid:
        raise ValueError(f"Training data is not usable: {validation_report.message}")

    dataframe = cleaning_result.dataframe.copy()
    for agent in [
        AmountAnomalyAgent(),
        VelocityFraudAgent(),
        UserBehaviorAgent(),
        MerchantRiskAgent(),
        LocationRiskAgent(),
        DuplicatePaymentAgent(),
    ]:
        agent.run(dataframe)
    return final_score_dataframe(dataframe)


def _calculate_metrics(model: RandomForestClassifier, x_val: pd.DataFrame, y_val: pd.Series) -> dict[str, float]:
    predictions = model.predict(x_val)
    metrics = {
        "accuracy": round(float(accuracy_score(y_val, predictions)), 4),
        "precision": round(float(precision_score(y_val, predictions, zero_division=0)), 4),
        "recall": round(float(recall_score(y_val, predictions, zero_division=0)), 4),
        "f1": round(float(f1_score(y_val, predictions, zero_division=0)), 4),
    }
    try:
        probabilities = model.predict_proba(x_val)[:, list(model.classes_).index(1)]
        metrics["roc_auc"] = round(float(roc_auc_score(y_val, probabilities)), 4)
    except Exception:
        pass
    return metrics


def train_model(input_path: str | None = None) -> dict:
    raw_dataframe = _load_training_dataframe(input_path)
    scored_dataframe = _score_with_existing_rules(raw_dataframe) if "fraud_score" not in raw_dataframe.columns else raw_dataframe.copy()

    label_source = "rule_fraud_score" if "rule_fraud_score" in scored_dataframe.columns else "fraud_score"
    labels = pd.to_numeric(scored_dataframe[label_source], errors="coerce").fillna(0.0).ge(61).astype(int)

    positive_labels = int(labels.sum())
    negative_labels = int(len(labels.index) - positive_labels)
    if len(labels.index) == 0:
        raise ValueError("No training rows were available after preprocessing.")

    if labels.nunique() < 2:
        message = (
            "Training skipped: only one label class was available. "
            "Existing model was not overwritten."
        )
        print(message)
        metadata = {
            "model_type": "RandomForestClassifier",
            "feature_columns": [],
            "label_rule": "fraud_label = 1 if rule_fraud_score >= 61 else 0",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "training_rows": int(len(labels.index)),
            "positive_labels": positive_labels,
            "negative_labels": negative_labels,
            "metrics": {},
            "status": "skipped_one_class",
            "message": message,
        }
        return metadata

    features, feature_columns = build_ml_features(scored_dataframe)
    y = labels

    can_split = len(features.index) >= 20 and labels.value_counts().min() >= 2
    metrics: dict[str, float] = {}

    if can_split:
        x_train, x_val, y_train, y_val = train_test_split(
            features,
            y,
            test_size=0.25,
            random_state=42,
            stratify=y,
        )
    else:
        x_train, y_train = features, y
        x_val = y_val = None

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )
    model.fit(x_train, y_train)

    if x_val is not None and y_val is not None:
        metrics = _calculate_metrics(model, x_val, y_val)

    metadata = {
        "model_type": "RandomForestClassifier",
        "feature_columns": feature_columns,
        "label_rule": "fraud_label = 1 if rule_fraud_score >= 61 else 0",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": int(len(features.index)),
        "positive_labels": positive_labels,
        "negative_labels": negative_labels,
        "metrics": metrics,
        "status": "trained",
    }

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": feature_columns}, MODEL_PATH)
    with METADATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, indent=2)

    print(f"Model saved: {MODEL_PATH}")
    print(json.dumps(metadata, indent=2))
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the SentinelPay AI lightweight ML fraud model.")
    parser.add_argument("--input", dest="input_path", default=None, help="Optional CSV/XLS/XLSX input path for training.")
    args = parser.parse_args()
    train_model(args.input_path)


if __name__ == "__main__":
    main()
