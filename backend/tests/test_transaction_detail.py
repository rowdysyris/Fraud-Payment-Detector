from __future__ import annotations

import io
from datetime import datetime, timedelta

import pandas as pd

from app.config import settings
from app.utils.constants import AGENT_SPECS
from tests.conftest import dataframe_to_csv_bytes, upload_csv


ALLOWED_REVIEW_STATUSES = ["Reviewed", "Confirmed Fraud", "Marked Safe"]


def _analysis_dataframe() -> pd.DataFrame:
    base = datetime(2026, 1, 1, 10, 0, 0)
    rows = []
    for index in range(16):
        rows.append(
            {
                "transaction_id": f"NORMAL{index:03d}",
                "user_id": f"USER{index % 6:03d}",
                "transaction_time": (base + timedelta(hours=index)).strftime("%Y-%m-%d %H:%M:%S"),
                "amount": 200 + index * 30,
                "merchant": f"Merchant{index % 5}",
                "location": "Mumbai",
                "payment_method": "UPI",
            }
        )
    for index in range(8):
        rows.append(
            {
                "transaction_id": f"VEL{index:03d}",
                "user_id": "USER999",
                "transaction_time": (base + timedelta(minutes=5, seconds=index * 20)).strftime("%Y-%m-%d %H:%M:%S"),
                "amount": 100 + index,
                "merchant": f"RapidShop{index}",
                "location": "Delhi",
                "payment_method": "Card",
            }
        )
    for index in range(5):
        rows.append(
            {
                "transaction_id": f"DUP{index:03d}",
                "user_id": "USER777",
                "transaction_time": (base + timedelta(minutes=30, seconds=index * 20)).strftime("%Y-%m-%d %H:%M:%S"),
                "amount": 2500,
                "merchant": "SameShop",
                "location": "Bangalore",
                "payment_method": "Wallet",
            }
        )
    rows.append(
        {
            "transaction_id": "HUGE001",
            "user_id": "USER001",
            "transaction_time": (base + timedelta(minutes=40)).strftime("%Y-%m-%d %H:%M:%S"),
            "amount": 999999,
            "merchant": "Luxury Merchant",
            "location": "Dubai",
            "payment_method": "Card",
        }
    )
    return pd.DataFrame(rows)


def _analyze(client, dataframe: pd.DataFrame | None = None) -> dict:
    csv = dataframe_to_csv_bytes(dataframe if dataframe is not None else _analysis_dataframe())
    response = upload_csv(client, csv)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["job_id"]
    return payload


def _first_transaction_id(payload: dict) -> str:
    rows = payload.get("sample_flagged_transactions") or payload.get("transactions") or []
    assert rows, "Expected at least one transaction row in analysis response."
    return str(rows[0]["transaction_id"])


def test_fetch_transaction_detail_contains_required_sections(client):
    payload = _analyze(client)
    transaction_id = _first_transaction_id(payload)
    response = client.get(f"/api/transaction-detail/{payload['job_id']}/{transaction_id}")
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["job_id"] == payload["job_id"]
    assert isinstance(detail["transaction"], dict)
    assert isinstance(detail["user_timeline"], list)
    assert isinstance(detail["agent_breakdown"], list)
    assert isinstance(detail["explanation"], dict)
    assert detail["transaction"]["transaction_id"] == transaction_id


def test_agent_breakdown_includes_all_major_agents(client):
    payload = _analyze(client)
    response = client.get(f"/api/transaction-detail/{payload['job_id']}/{_first_transaction_id(payload)}")
    assert response.status_code == 200
    names = {item["agent_name"] for item in response.json()["agent_breakdown"]}
    expected = {spec["display_name"] for spec in AGENT_SPECS.values()} | {"ML Fraud Model"}
    assert expected.issubset(names)
    for item in response.json()["agent_breakdown"]:
        assert "fired" in item
        assert isinstance(item["score_contribution"], (int, float))
        assert item["reason"]


def test_detail_explanation_has_manager_friendly_fields(client):
    payload = _analyze(client)
    response = client.get(f"/api/transaction-detail/{payload['job_id']}/{_first_transaction_id(payload)}")
    assert response.status_code == 200
    explanation = response.json()["explanation"]
    assert explanation["summary"]
    assert explanation["why_flagged"]
    assert isinstance(explanation["risk_evidence"], list)
    assert explanation["recommended_next_step"]
    assert "does not prove legal fraud" in explanation["disclaimer"]


def test_timeline_handles_invalid_dates(client):
    dataframe = _analysis_dataframe()
    dataframe.loc[0, "transaction_time"] = "not-a-date"
    dataframe.loc[1, "transaction_time"] = "99/99/9999"
    payload = _analyze(client, dataframe)
    response = client.get(f"/api/transaction-detail/{payload['job_id']}/{_first_transaction_id(payload)}")
    assert response.status_code == 200
    assert isinstance(response.json()["user_timeline"], list)


def test_timeline_handles_one_row_dataset(client):
    dataframe = pd.DataFrame(
        [
            {
                "transaction_id": "ONE001",
                "user_id": "USER001",
                "transaction_time": "2026-01-01 10:00:00",
                "amount": 1000,
                "merchant": "ShopA",
                "location": "Mumbai",
                "payment_method": "UPI",
            }
        ]
    )
    payload = _analyze(client, dataframe)
    response = client.get(f"/api/transaction-detail/{payload['job_id']}/ONE001")
    assert response.status_code == 200
    timeline = response.json()["user_timeline"]
    assert len(timeline) == 1
    assert timeline[0]["is_selected"] is True


def test_missing_job_id_returns_404(client):
    response = client.get("/api/transaction-detail/missing-job/T001")
    assert response.status_code == 404


def test_missing_transaction_id_returns_404(client):
    payload = _analyze(client)
    response = client.get(f"/api/transaction-detail/{payload['job_id']}/missing-transaction")
    assert response.status_code == 404


def test_patch_review_status_values_update_transaction(client):
    payload = _analyze(client)
    transaction_id = _first_transaction_id(payload)
    for status in ALLOWED_REVIEW_STATUSES:
        response = client.patch(
            f"/api/transaction-review/{payload['job_id']}/{transaction_id}",
            json={"review_status": status},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["transaction"]["review_status"] == status
        detail = client.get(f"/api/transaction-detail/{payload['job_id']}/{transaction_id}")
        assert detail.status_code == 200
        assert detail.json()["transaction"]["review_status"] == status


def test_patch_invalid_review_status_returns_400(client):
    payload = _analyze(client)
    response = client.patch(
        f"/api/transaction-review/{payload['job_id']}/{_first_transaction_id(payload)}",
        json={"review_status": "Invalid Status"},
    )
    assert response.status_code == 400


def test_review_status_is_persisted_to_csv(client):
    payload = _analyze(client)
    transaction_id = _first_transaction_id(payload)
    response = client.patch(
        f"/api/transaction-review/{payload['job_id']}/{transaction_id}",
        json={"review_status": "Confirmed Fraud"},
    )
    assert response.status_code == 200
    csv_response = client.get(f"/api/download/all-scored/{payload['job_id']}")
    assert csv_response.status_code == 200
    dataframe = pd.read_csv(io.BytesIO(csv_response.content), keep_default_na=False)
    updated = dataframe.loc[dataframe["transaction_id"].astype(str).eq(transaction_id)]
    assert not updated.empty
    assert set(updated["review_status"].astype(str)) == {"Confirmed Fraud"}


def test_existing_download_endpoints_still_work_after_review_update(client):
    payload = _analyze(client)
    transaction_id = _first_transaction_id(payload)
    response = client.patch(
        f"/api/transaction-review/{payload['job_id']}/{transaction_id}",
        json={"review_status": "Reviewed"},
    )
    assert response.status_code == 200
    for path in ["fraud-transactions", "all-scored", "summary-report"]:
        download = client.get(f"/api/download/{path}/{payload['job_id']}")
        assert download.status_code == 200
        assert download.content


def test_duplicate_transaction_id_review_updates_all_matches(client):
    dataframe = _analysis_dataframe()
    dataframe.loc[0:2, "transaction_id"] = "DUPLICATE-ID"
    payload = _analyze(client, dataframe)
    response = client.patch(
        f"/api/transaction-review/{payload['job_id']}/DUPLICATE-ID",
        json={"review_status": "Marked Safe"},
    )
    assert response.status_code == 200
    assert response.json()["updated_count"] == 3
    csv_response = client.get(f"/api/download/all-scored/{payload['job_id']}")
    dataframe = pd.read_csv(io.BytesIO(csv_response.content), keep_default_na=False)
    matching = dataframe.loc[dataframe["transaction_id"].astype(str).eq("DUPLICATE-ID")]
    assert len(matching.index) == 3
    assert set(matching["review_status"].astype(str)) == {"Marked Safe"}
