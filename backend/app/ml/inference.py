from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.ml.feature_engineering import FEATURE_COLUMNS, build_ml_features

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent / "model_store"
MODEL_PATH = MODEL_DIR / "fraud_model.joblib"
METADATA_PATH = MODEL_DIR / "fraud_model_metadata.json"

_REQUIRED_OUTPUT = {
    "fraud_score": 0,
    "confidence": 0.0,
    "fraud_pattern": "Normal",
    "fraud_reason": "No significant fraud signals detected",
    "triggered_agents": "ML Baseline",
    "risk_level": "Low Risk",
    "recommended_action": "Allow transaction",
    "review_status": "Auto Approved",
}


def _empty_probability(df: pd.DataFrame | None, reason: str = "model_unavailable") -> pd.Series:
    index = df.index if df is not None else None
    length = len(df.index) if df is not None else 0
    series = pd.Series([0.0] * length, index=index, dtype="float64")
    series.attrs["ml_model_available"] = False
    series.attrs["ml_warning"] = reason
    return series


def _load_metadata() -> dict[str, Any]:
    if not METADATA_PATH.exists():
        return {}
    try:
        with METADATA_PATH.open("r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as exc:
        logger.warning("Could not read ML metadata: %s", exc)
        return {}


def _load_model() -> Any | None:
    if not MODEL_PATH.exists():
        return None
    try:
        loaded = joblib.load(MODEL_PATH)
        if isinstance(loaded, dict) and "model" in loaded:
            return loaded["model"]
        return loaded
    except Exception as exc:
        logger.warning("Could not load ML fraud model: %s", exc)
        return None


def _aligned_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    features, generated_columns = build_ml_features(df)
    metadata = _load_metadata()
    feature_columns = metadata.get("feature_columns") or generated_columns or FEATURE_COLUMNS
    for column in feature_columns:
        if column not in features.columns:
            features[column] = 0.0
    aligned = features[feature_columns].apply(pd.to_numeric, errors="coerce")
    aligned = aligned.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    return aligned, list(feature_columns)


def predict_ml_fraud_probability(df: pd.DataFrame) -> pd.Series:
    """Return ML fraud probability as a 0-100 score for each row, preserving row order."""
    if df is None or len(df.index) == 0:
        return _empty_probability(df, "empty_dataframe")

    model = _load_model()
    if model is None:
        return _empty_probability(df, "model_file_missing")

    try:
        aligned_features, _ = _aligned_features(df)
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(aligned_features)
            classes = list(getattr(model, "classes_", []))
            if 1 in classes:
                positive_index = classes.index(1)
                scores = probabilities[:, positive_index] * 100.0
            else:
                scores = np.zeros(len(aligned_features.index), dtype="float64")
        else:
            predictions = model.predict(aligned_features)
            scores = pd.Series(predictions).astype(float).clip(0, 1).to_numpy() * 100.0

        series = pd.Series(scores, index=df.index, dtype="float64").clip(lower=0.0, upper=100.0).fillna(0.0)
        series.attrs["ml_model_available"] = True
        return series
    except Exception as exc:
        logger.warning("ML fraud inference failed safely: %s", exc)
        return _empty_probability(df, "inference_failed")


def _risk_level(score: int) -> str:
    if score >= 81:
        return "Critical Risk"
    if score >= 61:
        return "High Risk"
    if score >= 31:
        return "Medium Risk"
    return "Low Risk"


def _review_status(score: int) -> str:
    if score >= 81:
        return "Auto Block Recommended"
    if score >= 61:
        return "Manual Review Required"
    if score >= 31:
        return "Monitoring"
    return "Auto Approved"


def _action(risk: str) -> str:
    return {
        "Critical Risk": "Block payment and escalate to fraud team",
        "High Risk": "Send for manual review",
        "Medium Risk": "Monitor only",
        "Low Risk": "Allow transaction",
    }.get(risk, "Allow transaction")


def _feature_signal_score(features: pd.DataFrame) -> pd.Series:
    if features is None or features.empty:
        return pd.Series(dtype="float64")
    signal = pd.Series([0.0] * len(features.index), index=features.index, dtype="float64")

    amount_z_user = features.get("amount_zscore_vs_user", pd.Series(0, index=features.index)).astype(float)
    amount_z_global = features.get("amount_zscore_global", pd.Series(0, index=features.index)).astype(float)
    amount = features.get("amount", pd.Series(0, index=features.index)).astype(float)
    txns_10 = features.get("txns_in_10min", pd.Series(1, index=features.index)).astype(float)
    duplicate_count = features.get("duplicate_count", pd.Series(1, index=features.index)).astype(float)
    duplicate_tid = features.get("duplicate_transaction_id_flag", pd.Series(0, index=features.index)).astype(float)
    loc_diversity = features.get("user_location_diversity", pd.Series(1, index=features.index)).astype(float)

    signal = signal.mask(txns_10 >= 8, np.maximum(signal, 80))
    signal = signal.mask((txns_10 >= 5) & (txns_10 < 8), np.maximum(signal, 65))
    signal = signal.mask(amount_z_user >= 4, np.maximum(signal, 82))
    signal = signal.mask((amount_z_user >= 2.5) & (amount_z_user < 4), np.maximum(signal, 65))
    signal = signal.mask(amount_z_global >= 4, np.maximum(signal, 80))
    signal = signal.mask((amount_z_global >= 2.5) & (amount_z_global < 4), np.maximum(signal, 62))
    signal = signal.mask(amount >= 1000000, np.maximum(signal, 88))
    signal = signal.mask(duplicate_count >= 5, np.maximum(signal, 72))
    signal = signal.mask((duplicate_count >= 2) & (duplicate_count < 5), np.maximum(signal, 45))
    signal = signal.mask(duplicate_tid >= 1, np.maximum(signal, 60))
    signal = signal.mask(loc_diversity >= 4, np.maximum(signal, 55))
    return signal.clip(lower=0.0, upper=100.0).fillna(0.0)


def _patterns_and_reasons(row: pd.Series, score: int) -> tuple[str, str, str]:
    patterns: list[str] = []
    reasons: list[str] = []
    agents: list[str] = []

    if row.get("txns_in_10min", 1) >= 5:
        patterns.append("Velocity Fraud")
        reasons.append(f"{int(row.get('txns_in_10min', 0))} transactions occurred within a 10-minute user window")
        agents.append("ML Velocity Signal")
    if row.get("amount_zscore_vs_user", 0) >= 2.5 or row.get("amount_zscore_global", 0) >= 2.5 or row.get("amount", 0) >= 1000000:
        patterns.append("Amount Anomaly")
        reasons.append("Amount is statistically unusual compared with learned transaction patterns")
        agents.append("ML Amount Signal")
    if row.get("duplicate_count", 1) >= 2 or row.get("duplicate_transaction_id_flag", 0) >= 1:
        patterns.append("Duplicate Payment")
        reasons.append("Repeated transaction identifiers or user-merchant-amount combinations were detected")
        agents.append("ML Duplicate Signal")
    if row.get("user_location_diversity", 1) >= 4:
        patterns.append("Location Anomaly")
        reasons.append("User activity spans many distinct locations")
        agents.append("ML Location Signal")

    if not patterns:
        if score >= 31:
            patterns.append("ML Anomaly")
            reasons.append("RandomForest model assigned elevated fraud probability")
            agents.append("RandomForest Fraud Model")
        else:
            patterns.append("Normal")
            reasons.append("No significant fraud signals detected")
            agents.append("ML Baseline")

    return " + ".join(patterns), "; ".join(reasons), ", ".join(agents)


def _ensure_output_columns(result: pd.DataFrame) -> pd.DataFrame:
    for column, default in _REQUIRED_OUTPUT.items():
        if column not in result.columns:
            result[column] = default
    result["fraud_score"] = pd.to_numeric(result["fraud_score"], errors="coerce").fillna(0).clip(0, 100).astype(int)
    result["confidence"] = (result["fraud_score"] / 100).round(2)
    result["risk_level"] = result["fraud_score"].map(_risk_level)
    result["recommended_action"] = result["risk_level"].map(_action)
    result["review_status"] = result["fraud_score"].map(_review_status)
    for text_column in ["fraud_pattern", "fraud_reason", "triggered_agents"]:
        result[text_column] = result[text_column].fillna(_REQUIRED_OUTPUT[text_column]).astype(str).str.strip()
        result.loc[result[text_column].eq(""), text_column] = _REQUIRED_OUTPUT[text_column]
    return result


def run_inference(df: pd.DataFrame) -> pd.DataFrame:
    """Run standalone ML fraud inference and return the input rows plus fraud output columns."""
    if df is None:
        return _ensure_output_columns(pd.DataFrame())

    result = df.copy()
    if len(result.index) == 0:
        return _ensure_output_columns(result)

    features, _ = build_ml_features(result)
    ml_probability = predict_ml_fraud_probability(result).reindex(result.index).fillna(0.0).clip(lower=0.0, upper=100.0)
    signal_score = _feature_signal_score(features).reindex(result.index).fillna(0.0)
    fraud_score = pd.concat([ml_probability, signal_score], axis=1).max(axis=1).round(0).clip(lower=0, upper=100).astype(int)

    result["ml_fraud_probability"] = ml_probability.round(2)
    result["fraud_score"] = fraud_score
    patterns: list[str] = []
    reasons: list[str] = []
    agents: list[str] = []
    for idx in result.index:
        pattern, reason, triggered = _patterns_and_reasons(features.loc[idx], int(fraud_score.loc[idx]))
        patterns.append(pattern)
        reasons.append(reason)
        agents.append(triggered)
    result["fraud_pattern"] = patterns
    result["fraud_reason"] = reasons
    result["triggered_agents"] = agents
    return _ensure_output_columns(result)
