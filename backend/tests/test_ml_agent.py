from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.agents.final_risk_scoring_agent import FinalRiskScoringAgent
from app.ml.feature_engineering import FEATURE_COLUMNS, TARGET_LEAKAGE_COLUMNS, build_ml_features
from app.ml.inference import MODEL_PATH, predict_ml_fraud_probability


def _base_dataframe(rows: int = 8) -> pd.DataFrame:
    base = pd.Timestamp("2024-01-15 10:00:00")
    return pd.DataFrame(
        {
            "transaction_id": [f"TXN{i:04d}" for i in range(rows)],
            "user_id": [f"USER{i % 3:03d}" for i in range(rows)],
            "amount": [100.0, "₹5,000", "Rs. 2000", "INR 7500", "$250", "€400", "N/A", -500][:rows],
            "transaction_time": [(base + pd.Timedelta(minutes=i * 5)).strftime("%Y-%m-%d %H:%M:%S") for i in range(rows)],
            "merchant": ["Shop🔥" if i == 0 else f"Merchant {i % 3}" for i in range(rows)],
            "location": ["Mumbai" if i % 2 == 0 else "दिल्ली" for i in range(rows)],
            "payment_method": ["UPI" if i % 2 == 0 else "Card" for i in range(rows)],
            "fraud_score": [0, 25, 61, 80, 95, 5, 0, 35][:rows],
            "risk_level": ["Low Risk"] * rows,
            "fraud_pattern": ["Existing pattern"] * rows,
            "fraud_reason": ["Existing reason"] * rows,
            "triggered_agents": ["Existing Agent"] * rows,
            "confidence": [0.1] * rows,
            "recommended_action": ["Allow transaction"] * rows,
            "review_status": ["Auto Cleared"] * rows,
        }
    )


def test_ml_features_are_numeric_and_stable_order():
    features, columns = build_ml_features(_base_dataframe())
    assert list(features.columns) == FEATURE_COLUMNS
    assert columns == FEATURE_COLUMNS
    assert len(features) == 8
    assert all(pd.api.types.is_numeric_dtype(features[column]) for column in features.columns)
    assert features.notna().all().all()


def test_ml_features_do_not_include_target_leakage_columns():
    features, columns = build_ml_features(_base_dataframe())
    assert TARGET_LEAKAGE_COLUMNS.isdisjoint(set(columns))
    assert TARGET_LEAKAGE_COLUMNS.isdisjoint(set(features.columns))


def test_ml_feature_amount_parser_handles_currency_and_text():
    df = pd.DataFrame(
        {
            "amount": ["₹5,000", "Rs. 2000", "INR 7500", "$250", "€400", "12,000", " 3000 ", "N/A", None, "₹500😊", -500, 0],
            "user_id": ["U"] * 12,
            "transaction_time": ["2024-01-01"] * 12,
        }
    )
    features, _ = build_ml_features(df)
    assert features["amount"].tolist() == [5000.0, 2000.0, 7500.0, 250.0, 400.0, 12000.0, 3000.0, 0.0, 0.0, 500.0, -500.0, 0.0]


def test_ml_inference_returns_same_rows_and_valid_probability():
    df = _base_dataframe()
    probabilities = predict_ml_fraud_probability(df)
    assert len(probabilities) == len(df)
    assert probabilities.index.equals(df.index)
    assert probabilities.between(0, 100).all()


def test_ml_inference_missing_model_is_safe(monkeypatch):
    from app.ml import inference

    monkeypatch.setattr(inference, "MODEL_PATH", Path("/tmp/sentinelpay-missing-model.joblib"))
    probabilities = inference.predict_ml_fraud_probability(_base_dataframe(3))
    assert len(probabilities) == 3
    assert probabilities.eq(0).all()
    assert probabilities.attrs.get("ml_model_available") is False


def test_final_risk_scoring_agent_adds_rule_and_ml_columns():
    df = _base_dataframe(5).drop(
        columns=[
            "fraud_score",
            "risk_level",
            "fraud_pattern",
            "fraud_reason",
            "triggered_agents",
            "confidence",
            "recommended_action",
            "review_status",
        ]
    )
    df["amount_anomaly_score"] = [0, 20, 40, 45, 45]
    df["amount_anomaly_triggered"] = [False, True, True, True, True]
    df["amount_anomaly_reason"] = ["", "amount signal", "amount signal", "amount signal", "amount signal"]
    df["amount_anomaly_pattern"] = ["None", "Amount Anomaly", "Amount Anomaly", "Amount Anomaly", "Amount Anomaly"]

    result = FinalRiskScoringAgent().run(df)
    assert result.status.startswith("completed")
    assert "rule_fraud_score" in df.columns
    assert "ml_fraud_probability" in df.columns
    assert "fraud_score" in df.columns
    assert df["rule_fraud_score"].between(0, 100).all()
    assert df["ml_fraud_probability"].between(0, 100).all()
    assert df["fraud_score"].between(0, 100).all()
    assert set(df["risk_level"]).issubset({"Low Risk", "Medium Risk", "High Risk", "Critical Risk"})


def test_one_row_dataset_does_not_crash():
    df = _base_dataframe(1)
    features, _ = build_ml_features(df)
    probabilities = predict_ml_fraud_probability(df)
    assert len(features) == 1
    assert len(probabilities) == 1
    assert probabilities.between(0, 100).all()


def test_missing_optional_columns_do_not_crash():
    df = pd.DataFrame(
        {
            "user_id": ["USER001", "USER002"],
            "amount": [100, 250],
            "transaction_time": ["2024-01-01", "2024-01-02"],
        }
    )
    features, _ = build_ml_features(df)
    probabilities = predict_ml_fraud_probability(df)
    assert len(features) == 2
    assert len(probabilities) == 2
    assert probabilities.between(0, 100).all()


def test_missing_user_id_does_not_crash():
    df = pd.DataFrame(
        {
            "transaction_id": ["T1", "T2"],
            "amount": [100, 250],
            "transaction_time": ["2024-01-01", "2024-01-02"],
        }
    )
    features, _ = build_ml_features(df)
    probabilities = predict_ml_fraud_probability(df)
    assert len(features) == 2
    assert len(probabilities) == 2
    assert probabilities.between(0, 100).all()


def test_invalid_dates_do_not_crash():
    df = _base_dataframe(5)
    df["transaction_time"] = ["not-a-date", "99/99/9999", "", None, "2024-01-15"]
    features, _ = build_ml_features(df)
    probabilities = predict_ml_fraud_probability(df)
    assert len(features) == 5
    assert len(probabilities) == 5
    assert features["hour_of_day"].notna().all()


def test_weird_merchant_location_strings_do_not_crash():
    df = _base_dataframe(4)
    df["merchant"] = ["Store<script>alert(1)</script>", "दुकान", "Shop🔥", "VeryLong" * 80]
    df["location"] = ["Mumbai\nNorth", "北京", "دبي", "New York ⭐"]
    features, _ = build_ml_features(df)
    probabilities = predict_ml_fraud_probability(df)
    assert len(features) == 4
    assert len(probabilities) == 4
    assert probabilities.between(0, 100).all()


def test_extreme_values_and_infinite_values_do_not_crash():
    df = pd.DataFrame(
        {
            "transaction_id": ["T1", "T2", "T3"],
            "user_id": ["U1", "U1", "U2"],
            "amount": [999999999999.99, float("inf"), "-inf"],
            "transaction_time": ["2099-12-31", "2024-01-01", "bad-date"],
            "merchant": ["A", "B", "C"],
            "location": ["Mumbai", "Dubai", "London"],
            "payment_method": ["UPI", "Card", "Wallet"],
        }
    )
    features, _ = build_ml_features(df)
    probabilities = predict_ml_fraud_probability(df)
    assert len(features) == 3
    assert len(probabilities) == 3
    assert features.replace([float("inf"), float("-inf")], pd.NA).notna().all().all()
    assert probabilities.between(0, 100).all()
