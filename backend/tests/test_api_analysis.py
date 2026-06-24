import io

import pandas as pd

from tests.conftest import (
    FINAL_OUTPUT_COLUMNS,
    assert_clear_validation_response,
    assert_scored_csv_response,
    assert_success_payload,
    rows_to_csv_bytes,
    standard_rows,
    upload_csv,
    upload_raw_csv,
)


def test_api_analyzes_perfect_standard_transaction_dataset(client) -> None:
    response = upload_csv(client, rows_to_csv_bytes(standard_rows()))

    assert response.status_code == 200
    payload = response.json()
    assert_success_payload(payload)
    scored = assert_scored_csv_response(client, payload)
    assert len(scored) == len(standard_rows())


def test_api_analyzes_messy_schema_dataset(client) -> None:
    rows = [
        {
            "txn_id": "M1",
            "customer": "U1",
            "payment_date": "2026-01-01 10:00:00",
            "txn_amt": "₹1,200",
            "shop_name": "Messy Store",
            "city": "Bhopal",
            "payment_mode": "UPI",
            "result": "success",
            "curr": "INR",
            "extra_noise": "ignored but preserved",
        },
        {
            "txn_id": "M2",
            "customer": "U1",
            "payment_date": "2026-01-01 10:04:00",
            "txn_amt": "Rs. 2,500",
            "shop_name": "Another Store",
            "city": "Delhi",
            "payment_mode": "Card",
            "result": "success",
            "curr": "INR",
            "extra_noise": "ignored but preserved",
        },
    ]

    response = upload_csv(client, rows_to_csv_bytes(rows))

    assert response.status_code == 200
    payload = response.json()
    assert_success_payload(payload)
    assert payload["ingestion_metadata"]["mapped_columns"]["amount"] == "txn_amt"
    scored = assert_scored_csv_response(client, payload)
    assert "extra_noise" in scored.columns
    assert scored["amount"].tolist() == [1200.0, 2500.0]


def test_api_analyzes_minimum_required_columns_and_missing_optional_columns(client) -> None:
    rows = [
        {"customer_id": "U1", "created_at": "2026-01-01 10:00:00", "value": "100"},
        {"customer_id": "U2", "created_at": "2026-01-02 10:00:00", "value": "200"},
    ]

    response = upload_csv(client, rows_to_csv_bytes(rows))

    assert response.status_code == 200
    payload = response.json()
    assert_success_payload(payload)
    scored = assert_scored_csv_response(client, payload)
    assert set(["merchant", "location", "payment_method", "status", "currency"]).issubset(scored.columns)
    assert scored["transaction_id"].notna().all()


def test_api_returns_clear_400_for_missing_required_columns(client) -> None:
    missing_amount = "user_id,transaction_time,merchant\nU1,2026-01-01,Store A\n"
    missing_user = "amount,transaction_time,merchant\n100,2026-01-01,Store A\n"
    missing_time = "user_id,amount,merchant\nU1,100,Store A\n"

    for content, expected in [
        (missing_amount, "amount"),
        (missing_user, "user_id"),
        (missing_time, "transaction_time"),
    ]:
        response = upload_raw_csv(client, content)
        assert response.status_code == 400
        assert expected in response.json()["detail"]


def test_api_returns_clear_400_for_empty_and_headers_only_csv(client) -> None:
    empty_response = upload_raw_csv(client, b"", filename="empty.csv")
    assert empty_response.status_code == 400
    assert "empty" in empty_response.json()["detail"].lower()

    headers_response = upload_raw_csv(client, "transaction_id,user_id,transaction_time,amount\n", filename="headers.csv")
    assert headers_response.status_code == 400
    assert "headers" in headers_response.json()["detail"].lower()


def test_api_rejects_unsupported_files(client) -> None:
    response = client.post(
        "/api/analyze",
        files={"file": ("transactions.txt", io.BytesIO(b"hello"), "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_api_download_endpoints_for_successful_job(client) -> None:
    response = upload_csv(client, rows_to_csv_bytes(standard_rows()))
    assert response.status_code == 200
    payload = response.json()
    job_id = payload["job_id"]

    endpoints = [
        (f"/api/download/fraud-transactions/{job_id}", "text/csv"),
        (f"/api/download/all-scored/{job_id}", "text/csv"),
        (f"/api/download/summary-report/{job_id}", "application/pdf"),
    ]
    for endpoint, expected_type in endpoints:
        download = client.get(endpoint)
        assert download.status_code == 200
        assert download.content
        assert expected_type in download.headers["content-type"]

    fraud_csv = client.get(f"/api/download/fraud-transactions/{job_id}")
    fraud_dataframe = pd.read_csv(io.BytesIO(fraud_csv.content))
    if not fraud_dataframe.empty:
        assert set(fraud_dataframe["risk_level"]).issubset({"Medium Risk", "High Risk", "Critical Risk"})

    missing = client.get("/api/download/all-scored/not-a-real-job")
    assert missing.status_code == 404
    assert missing.json()["detail"]


def test_successful_analysis_preview_contains_final_output_columns(client) -> None:
    response = upload_csv(client, rows_to_csv_bytes(standard_rows()))
    assert response.status_code == 200
    payload = response.json()

    assert payload["preview"]
    first_row = payload["preview"][0]
    for column in FINAL_OUTPUT_COLUMNS:
        assert column in first_row
