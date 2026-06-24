import pytest
import io
import pandas as pd
import numpy as np
from httpx import AsyncClient, ASGITransport
from app.main import app

pytestmark = pytest.mark.asyncio


def df_to_bytes(df):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.read()


async def upload(client, content, filename="test.csv"):
    files = {"file": (filename, content, "text/csv")}
    return await client.post("/api/analyze", files=files)


def base_df(rows=30):
    base_time = pd.Timestamp("2024-01-15 10:00:00")
    return pd.DataFrame(
        {
            "transaction_id": [f"TXN{i:05d}" for i in range(rows)],
            "user_id": [f"USER{(i % 100) + 1:03d}" for i in range(rows)],
            "amount": [float(100 + (i % 20) * 45) for i in range(rows)],
            "transaction_time": [(base_time + pd.Timedelta(minutes=i * 7)).strftime("%Y-%m-%d %H:%M:%S") for i in range(rows)],
            "merchant": [f"Merchant {i % 8}" for i in range(rows)],
            "location": [["Mumbai", "Delhi", "Bangalore", "Chennai", "Pune"][i % 5] for i in range(rows)],
            "payment_method": [["UPI", "Card", "Wallet", "Net Banking"][i % 4] for i in range(rows)],
        }
    )


def assert_clear_error(response):
    assert response.status_code != 500, response.text
    body = response.json()
    assert any(body.get(key) for key in ["error", "message", "detail", "validation_errors"]), body


async def test_one_column_csv():
    df = pd.DataFrame({"amount": [100, 200, 300]})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert_clear_error(response)


async def test_100_column_csv():
    df = base_df(30)[["transaction_id", "user_id", "amount", "transaction_time"]].copy()
    for idx in range(1, 98):
        df[f"extra_col_{idx}"] = [f"value_{idx}_{row}" for row in range(30)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert len(body["transactions"]) == 30


async def test_all_same_timestamp():
    df = base_df(100)
    df["transaction_time"] = "2024-01-15 10:00:00"
    df["user_id"] = [f"USER{i + 1:03d}" for i in range(100)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 100


async def test_all_same_user():
    df = base_df(200)
    df["user_id"] = "USER001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 200


async def test_all_same_amount():
    df = base_df(100)
    df["amount"] = 1000.0
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 100


async def test_unicode_merchant_names():
    names = [
        "दुकान",
        "बाजार",
        "स्टोर",
        "متجر",
        "محل",
        "商店",
        "超市",
        "お店",
        "コンビニ",
        "Shop🔥",
        "Store⭐",
    ]
    df = base_df(30)
    df["merchant"] = [names[i % len(names)] for i in range(30)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
        assert response.status_code == 200, response.text
        job_id = response.json()["job_id"]
        pdf_response = await client.get(f"/api/download/summary-report/{job_id}")
    assert pdf_response.status_code == 200, pdf_response.text
    assert pdf_response.content.startswith(b"%PDF")


async def test_extremely_large_single_amount():
    df = base_df(20)
    df.loc[7, "amount"] = 999999999999.99
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    tx = response.json()["transactions"][7]
    assert tx["fraud_score"] > 40


async def test_special_characters_in_ids():
    special_users = ["USER@#$%", "USER<001>", "USER\nXYZ", "USER;DROP", "USER'001", 'USER"XYZ']
    special_merchants = ["Store<script>alert(1)</script>", "Shop & Co. / Branch\nNew", "Cafe 'Best'"]
    df = base_df(30)
    df["user_id"] = [special_users[i % len(special_users)] for i in range(30)]
    df["merchant"] = [special_merchants[i % len(special_merchants)] for i in range(30)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 30


async def test_bom_csv():
    df = base_df(20)
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    content = buf.getvalue()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, content)
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 20


async def test_completely_missing_optional_columns():
    df = base_df(30)[["user_id", "amount", "transaction_time"]].copy()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["transactions"]) == 30
    assert all("fraud_score" in row for row in body["transactions"])


async def test_amount_column_all_text():
    values = ["unknown", "pending", "processing", "error", "TBD"]
    df = base_df(20)
    df["amount"] = [values[i % len(values)] for i in range(20)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code != 500, response.text
    if response.status_code == 200:
        assert len(response.json()["transactions"]) == 20
    else:
        assert_clear_error(response)


async def test_very_long_transaction_ids():
    df = base_df(20)
    df["transaction_id"] = [("TXN" + str(i) + "X" * 500) for i in range(20)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 20


async def test_refund_transactions():
    df = base_df(30)
    df.loc[0:9, "amount"] = [500 + i * 100 for i in range(10)]
    df.loc[10:19, "amount"] = [-500 + i * 40 for i in range(10)]
    df.loc[20:29, "amount"] = 0
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 30
    assert all("fraud_score" in row for row in response.json()["transactions"])


async def test_future_dates():
    df = base_df(20)
    future_values = ["2099-12-31 23:59:59", "2050-01-01 00:00:00", "2077-07-07 07:07:07"]
    df["transaction_time"] = [future_values[i % len(future_values)] for i in range(20)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 20


async def test_duplicate_transaction_ids():
    df = base_df(30)
    df["transaction_id"] = "TXN001"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["transactions"]) == 30
    assert any("duplicate" in str(row.get("fraud_pattern", "")).lower() or "duplicate" in str(row.get("triggered_agents", "")).lower() for row in body["transactions"])
