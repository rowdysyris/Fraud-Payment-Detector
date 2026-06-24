from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

FINAL_OUTPUT_COLUMNS = [
    "fraud_score",
    "risk_level",
    "fraud_pattern",
    "fraud_reason",
    "triggered_agents",
    "confidence",
    "recommended_action",
    "review_status",
]

RISK_LEVELS = {"Low Risk", "Medium Risk", "High Risk", "Critical Risk"}


@pytest.fixture()
def client(tmp_path: Path) -> Iterable[TestClient]:
    storage_dir = tmp_path / "storage"
    object.__setattr__(settings, "storage_dir", storage_dir)
    with TestClient(app) as test_client:
        yield test_client


def dataframe_to_csv_bytes(dataframe: pd.DataFrame) -> io.BytesIO:
    buffer = io.BytesIO()
    dataframe.to_csv(buffer, index=False)
    buffer.seek(0)
    return buffer


def rows_to_csv_bytes(rows: list[dict[str, Any]], columns: list[str] | None = None) -> io.BytesIO:
    dataframe = pd.DataFrame(rows, columns=columns)
    return dataframe_to_csv_bytes(dataframe)


def upload_csv(client: TestClient, csv_buffer: io.BytesIO, filename: str = "transactions.csv"):
    csv_buffer.seek(0)
    return client.post(
        "/api/analyze",
        files={"file": (filename, csv_buffer, "text/csv")},
    )


def upload_raw_csv(client: TestClient, content: str | bytes, filename: str = "transactions.csv"):
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return upload_csv(client, io.BytesIO(raw), filename=filename)


def standard_rows() -> list[dict[str, Any]]:
    return [
        {
            "transaction_id": "T001",
            "user_id": "U001",
            "transaction_time": "2026-01-01 10:00:00",
            "amount": "120.50",
            "merchant": "Daily Store",
            "location": "Bhopal",
            "payment_method": "UPI",
            "status": "success",
            "currency": "INR",
        },
        {
            "transaction_id": "T002",
            "user_id": "U001",
            "transaction_time": "2026-01-01 10:04:00",
            "amount": "150",
            "merchant": "Coffee Hub",
            "location": "Bhopal",
            "payment_method": "UPI",
            "status": "success",
            "currency": "INR",
        },
        {
            "transaction_id": "T003",
            "user_id": "U002",
            "transaction_time": "2026-01-01 11:00:00",
            "amount": "9000",
            "merchant": "Electronics World",
            "location": "Indore",
            "payment_method": "Card",
            "status": "success",
            "currency": "INR",
        },
        {
            "transaction_id": "T004",
            "user_id": "U003",
            "transaction_time": "2026-01-01 12:00:00",
            "amount": "0",
            "merchant": "Refund Desk",
            "location": "Mumbai",
            "payment_method": "Wallet",
            "status": "refund",
            "currency": "INR",
        },
    ]


def minimal_rows() -> list[dict[str, Any]]:
    return [
        {"user_id": "U001", "transaction_time": "2026-01-01 10:00:00", "amount": "100"},
        {"user_id": "U002", "transaction_time": "2026-01-01 10:03:00", "amount": "250"},
    ]


def assert_clear_validation_response(response) -> None:
    assert response.status_code in {400, 422}
    payload = response.json()
    assert "detail" in payload
    assert payload["detail"]
    assert isinstance(payload["detail"], (str, dict, list))


def assert_success_payload(payload: dict[str, Any]) -> None:
    assert payload["status"] in {"completed", "success"}
    assert payload["job_id"]
    assert payload["total_transactions"] >= 1
    assert payload["valid_transactions"] >= 1
    assert isinstance(payload["risk_distribution"], dict)
    assert set(payload["risk_distribution"].keys()) == RISK_LEVELS
    assert isinstance(payload["agent_summary"], dict)
    assert payload["download_urls"]["fraud_transactions"]
    assert payload["download_urls"]["all_scored"]
    assert payload["download_urls"]["summary_report"]
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["validation_errors"], list)
    assert isinstance(payload["sample_flagged_transactions"], list)


def assert_scored_csv_response(client: TestClient, payload: dict[str, Any]) -> pd.DataFrame:
    job_id = payload["job_id"]
    response = client.get(f"/api/download/all-scored/{job_id}")
    assert response.status_code == 200
    dataframe = pd.read_csv(io.BytesIO(response.content))
    for column in FINAL_OUTPUT_COLUMNS:
        assert column in dataframe.columns
    assert dataframe["fraud_score"].between(0, 100).all()
    assert set(dataframe["risk_level"].dropna()).issubset(RISK_LEVELS)
    assert dataframe["recommended_action"].notna().all()
    return dataframe
