from __future__ import annotations

import io
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.ml import inference

client = TestClient(app)
MODEL_PATH = inference.MODEL_PATH
METADATA_PATH = inference.METADATA_PATH
ML_FIELDS = {"rule_fraud_score", "ml_fraud_probability", "fraud_score"}


def _csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer.read()


def _standard_df(n: int = 40) -> pd.DataFrame:
    base = datetime(2024, 1, 15, 10, 0, 0)
    return pd.DataFrame(
        {
            "transaction_id": [f"TXN{i:04d}" for i in range(n)],
            "user_id": [f"USER{i % 10 + 1:03d}" for i in range(n)],
            "amount": [float(250 + (i % 12) * 35) for i in range(n)],
            "transaction_time": [(base + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)],
            "merchant": [f"Merchant{i % 6}" for i in range(n)],
            "location": [["Mumbai", "Delhi", "Bangalore"][i % 3] for i in range(n)],
            "payment_method": [["UPI", "Card", "Wallet"][i % 3] for i in range(n)],
        }
    )


def _stress_df() -> pd.DataFrame:
    base = datetime(2024, 1, 15, 10, 0, 0)
    rows: list[dict] = []
    for i in range(15):
        rows.append(
            {
                "transaction_id": f"NORMAL{i}",
                "user_id": f"NORMAL_USER{i % 5}",
                "amount": float(300 + i * 5),
                "transaction_time": (base + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": "NormalShop",
                "location": "Mumbai",
                "payment_method": "UPI",
            }
        )
    rows.append(
        {
            "transaction_id": "LARGE_AMOUNT",
            "user_id": "USER_LARGE",
            "amount": 100000.0,
            "transaction_time": (base + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S"),
            "merchant": "LuxuryStore",
            "location": "Dubai",
            "payment_method": "Card",
        }
    )
    for i in range(8):
        rows.append(
            {
                "transaction_id": f"VELOCITY{i}",
                "user_id": "USER_VELOCITY",
                "amount": float(100 + i),
                "transaction_time": (base + timedelta(seconds=i * 30)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": f"VelocityShop{i}",
                "location": "Delhi",
                "payment_method": "Card",
            }
        )
    for i in range(5):
        rows.append(
            {
                "transaction_id": "DUPLICATE_ID",
                "user_id": "USER_DUPLICATE",
                "amount": 2500.0,
                "transaction_time": (base + timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": "SameShop",
                "location": "Pune",
                "payment_method": "Wallet",
            }
        )
    for i, location in enumerate(["Mumbai", "Dubai", "London", "Singapore"]):
        rows.append(
            {
                "transaction_id": f"LOCATION{i}",
                "user_id": "USER_LOCATION",
                "amount": 800.0,
                "transaction_time": (base + timedelta(minutes=i * 10)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": "TravelShop",
                "location": location,
                "payment_method": "UPI",
            }
        )
    rows.append(
        {
            "transaction_id": "ZERO_AMOUNT",
            "user_id": "USER_ZERO",
            "amount": 0.0,
            "transaction_time": (base + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "merchant": "ZeroShop",
            "location": "Mumbai",
            "payment_method": "UPI",
        }
    )
    rows.append(
        {
            "transaction_id": "NEGATIVE_AMOUNT",
            "user_id": "USER_NEGATIVE",
            "amount": -500.0,
            "transaction_time": (base + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S"),
            "merchant": "RefundShop",
            "location": "Mumbai",
            "payment_method": "Card",
        }
    )
    locations = ["Mumbai", "Dubai", "London", "Singapore", "New York", "Delhi", "Tokyo", "Paris"]
    for i in range(8):
        rows.append(
            {
                "transaction_id": "MULTI_SIGNAL_DUP",
                "user_id": "USER_MULTI_SIGNAL",
                "amount": 100000.0,
                "transaction_time": (base + timedelta(seconds=i * 30)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": "MultiFraudShop",
                "location": locations[i],
                "payment_method": "Card",
            }
        )
    return pd.DataFrame(rows)


def _upload(df: pd.DataFrame, filename: str = "input.csv"):
    return client.post("/api/analyze", files={"file": (filename, _csv_bytes(df), "text/csv")})


@contextmanager
def _temporarily_replace(path: Path, replacement: bytes | None):
    backup = None
    existed = path.exists()
    if existed:
        backup = path.read_bytes()
    try:
        if replacement is None:
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(replacement)
        yield
    finally:
        if existed and backup is not None:
            path.write_bytes(backup)
        elif path.exists():
            path.unlink()


def _assert_response_has_ml_fields(data: dict) -> None:
    assert data.get("job_id")
    assert data.get("download_urls")
    assert data.get("transactions")
    first = data["transactions"][0]
    assert ML_FIELDS.issubset(first.keys())
    flagged = data.get("sample_flagged_transactions") or []
    if flagged:
        assert ML_FIELDS.issubset(flagged[0].keys())


def test_api_response_contains_ml_fields_and_download_urls():
    response = _upload(_standard_df(50))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    _assert_response_has_ml_fields(data)


def test_downloaded_csvs_include_ml_fields_and_pdf_downloads():
    response = _upload(_stress_df(), "stress.csv")
    assert response.status_code == 200, response.text
    data = response.json()
    job_id = data["job_id"]

    fraud_csv = client.get(f"/api/download/fraud-transactions/{job_id}")
    assert fraud_csv.status_code == 200
    fraud_df = pd.read_csv(io.BytesIO(fraud_csv.content))
    assert ML_FIELDS.issubset(fraud_df.columns)

    all_csv = client.get(f"/api/download/all-scored/{job_id}")
    assert all_csv.status_code == 200
    all_df = pd.read_csv(io.BytesIO(all_csv.content))
    assert ML_FIELDS.issubset(all_df.columns)
    assert len(all_df) == len(_stress_df())

    pdf = client.get(f"/api/download/summary-report/{job_id}")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_download_missing_job_returns_404():
    for endpoint in ["fraud-transactions", "all-scored", "summary-report"]:
        response = client.get(f"/api/download/{endpoint}/missing-job-id")
        assert response.status_code == 404


def test_api_does_not_crash_when_model_missing():
    with _temporarily_replace(MODEL_PATH, None):
        response = _upload(_stress_df(), "missing_model.csv")
    assert response.status_code == 200, response.text
    data = response.json()
    rows = pd.DataFrame(data["transactions"])
    assert ML_FIELDS.issubset(rows.columns)
    assert rows["ml_fraud_probability"].fillna(0).eq(0).all()
    assert rows["rule_fraud_score"].between(0, 100).all()
    assert rows["fraud_score"].between(0, 100).all()


def test_api_does_not_crash_when_metadata_missing():
    with _temporarily_replace(METADATA_PATH, None):
        response = _upload(_stress_df(), "missing_metadata.csv")
    assert response.status_code == 200, response.text
    rows = pd.DataFrame(response.json()["transactions"])
    assert ML_FIELDS.issubset(rows.columns)
    assert rows["ml_fraud_probability"].between(0, 100).all()


def test_api_does_not_crash_when_model_corrupted():
    with _temporarily_replace(MODEL_PATH, b"not a valid joblib model"):
        response = _upload(_stress_df(), "corrupt_model.csv")
    assert response.status_code == 200, response.text
    rows = pd.DataFrame(response.json()["transactions"])
    assert ML_FIELDS.issubset(rows.columns)
    assert rows["ml_fraud_probability"].fillna(0).eq(0).all()
    assert rows["fraud_score"].between(0, 100).all()


def test_fraud_stress_scoring_calibration():
    response = _upload(_stress_df(), "fraud_stress.csv")
    assert response.status_code == 200, response.text
    rows = pd.DataFrame(response.json()["transactions"])
    assert rows["fraud_score"].between(0, 100).all()

    normal = rows[rows["transaction_id"].astype(str).str.startswith("NORMAL")]["fraud_score"]
    large = rows[rows["transaction_id"].eq("LARGE_AMOUNT")]["fraud_score"]
    velocity = rows[rows["transaction_id"].astype(str).str.startswith("VELOCITY")]["fraud_score"]
    duplicate = rows[rows["transaction_id"].eq("DUPLICATE_ID")]["fraud_score"]
    multi = rows[rows["transaction_id"].eq("MULTI_SIGNAL_DUP")]["fraud_score"]

    assert large.max() > normal.mean()
    assert velocity.mean() > normal.mean()
    assert duplicate.mean() > normal.mean()
    assert multi.mean() > normal.mean()
    assert rows["risk_level"].isin(["Medium Risk", "High Risk", "Critical Risk"]).any()
    assert rows["risk_level"].isin(["High Risk", "Critical Risk"]).any()
    assert multi.max() >= 81

    for _, row in rows.iterrows():
        score = int(row["fraud_score"])
        risk = row["risk_level"]
        if score <= 30:
            assert risk == "Low Risk"
        elif score <= 60:
            assert risk == "Medium Risk"
        elif score <= 80:
            assert risk == "High Risk"
        else:
            assert risk == "Critical Risk"
