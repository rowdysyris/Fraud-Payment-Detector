import pytest
import io
import pandas as pd
import openpyxl
from httpx import AsyncClient, ASGITransport
from app.main import app

pytestmark = pytest.mark.asyncio


def df_to_bytes(df):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.read()


async def upload_file(client, content, filename="test.csv", content_type="text/csv"):
    files = {"file": (filename, content, content_type)}
    response = await client.post("/api/analyze", files=files)
    return response


def standard_df(rows=20):
    base = pd.Timestamp("2024-01-15 10:00:00")
    return pd.DataFrame(
        {
            "transaction_id": [f"TXN{i:04d}" for i in range(rows)],
            "user_id": [f"USER{i % 5:03d}" for i in range(rows)],
            "amount": [float(100 + (i % 10) * 50) for i in range(rows)],
            "transaction_time": [(base + pd.Timedelta(minutes=i * 5)).strftime("%Y-%m-%d %H:%M:%S") for i in range(rows)],
            "merchant": [f"Merchant {i % 4}" for i in range(rows)],
            "location": [["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai"][i % 5] for i in range(rows)],
            "payment_method": [["UPI", "Card", "Wallet", "Net Banking"][i % 4] for i in range(rows)],
        }
    )


async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_clean_csv_upload():
    df = standard_df(50)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert len(body["transactions"]) == 50
    required_keys = {
        "fraud_score",
        "risk_level",
        "fraud_reason",
        "recommended_action",
        "triggered_agents",
        "confidence",
        "review_status",
        "fraud_pattern",
    }
    for row in body["transactions"]:
        assert required_keys.issubset(row.keys())


async def test_messy_column_names():
    rows = 30
    base = pd.Timestamp("2024-01-15 10:00:00")
    df = pd.DataFrame(
        {
            "txn_ref": [f"M{i:04d}" for i in range(rows)],
            "customer": [f"USER{i % 5:03d}" for i in range(rows)],
            "txn_amt": [100 + i for i in range(rows)],
            "payment_date": [(base + pd.Timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(rows)],
            "shop_name": [f"Shop {i % 3}" for i in range(rows)],
            "city": [["Mumbai", "Delhi", "Pune"][i % 3] for i in range(rows)],
            "mode": [["UPI", "Card", "Wallet"][i % 3] for i in range(rows)],
        }
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"


async def test_currency_cleaning():
    amounts = ["₹5,000", "Rs. 2000", "INR 7500", "$250", "€400", "12,000", " 3000 ", "Rs.500", "INR1000", "7500.50"]
    base = pd.Timestamp("2024-01-15 10:00:00")
    df = pd.DataFrame(
        {
            "transaction_id": [f"CUR{i:03d}" for i in range(len(amounts))],
            "user_id": [f"USER{i % 3:03d}" for i in range(len(amounts))],
            "amount": amounts,
            "transaction_time": [(base + pd.Timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(len(amounts))],
            "merchant": ["Currency Shop"] * len(amounts),
            "location": ["Mumbai"] * len(amounts),
            "payment_method": ["UPI"] * len(amounts),
        }
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    for row in body["transactions"]:
        assert isinstance(row["amount"], (float, int))
        assert row["amount"] > 0


async def test_empty_file():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, b"", filename="empty.csv")
    assert response.status_code != 500
    body = response.json()
    assert any(body.get(key) for key in ["error", "message", "detail"])


async def test_headers_only():
    content = b"transaction_id,user_id,amount,transaction_time\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, content)
    assert response.status_code != 500
    body = response.json()
    message = str(body.get("error") or body.get("message") or body.get("detail") or "")
    assert message


async def test_missing_amount_column():
    df = standard_df(20).drop(columns=["amount"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code != 500
    body = response.json()
    message = str(body.get("error") or body.get("message") or body.get("detail") or "")
    assert "amount" in message.lower()


async def test_missing_user_id():
    df = standard_df(20).drop(columns=["user_id"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code != 500
    body = response.json()
    assert response.status_code == 200 or any(body.get(key) for key in ["error", "message", "detail"])


async def test_missing_transaction_time():
    df = standard_df(20).drop(columns=["transaction_time"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code != 500
    body = response.json()
    assert response.status_code == 200 or any(body.get(key) for key in ["error", "message", "detail"])


async def test_all_amounts_null():
    df = standard_df(20)
    df["amount"] = ["" if i % 2 == 0 else "N/A" for i in range(20)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code != 500
    body = response.json()
    assert response.status_code == 200 or any(body.get(key) for key in ["error", "message", "detail"])


async def test_invalid_dates():
    values = ["not-a-date", "99/99/9999", "", "abc", "32/13/2024", None, "2024-01-15", "15-01-2024"]
    df = standard_df(15)
    df["transaction_time"] = [values[i % len(values)] for i in range(15)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text


async def test_negative_amounts():
    df = standard_df(20)
    df.loc[:4, "amount"] = -500
    df.loc[5:9, "amount"] = -1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text


async def test_zero_amounts():
    df = standard_df(20)
    df["amount"] = 0
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code != 500
    assert "transactions" in response.json()


async def test_duplicate_rows():
    df = standard_df(10)
    df = pd.concat([df, df], ignore_index=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code != 500
    assert "transactions" in response.json()


async def test_single_row_dataset():
    df = standard_df(1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 1


def transaction_text(row):
    parts = []
    for key in ["fraud_pattern", "triggered_agents", "fraud_reason"]:
        value = row.get(key, "")
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


async def test_velocity_fraud_detected():
    base = pd.Timestamp("2024-01-01 09:00:00")
    rows = []
    for i in range(20):
        rows.append(
            {
                "transaction_id": f"NORMV{i:04d}",
                "user_id": f"USER{i + 1:03d}",
                "amount": 200 + (i % 7) * 40,
                "transaction_time": (base + pd.Timedelta(hours=i * 3)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": f"Normal Merchant {i % 5}",
                "location": "Mumbai",
                "payment_method": "Card",
            }
        )
    burst_start = pd.Timestamp("2024-01-04 12:00:00")
    for i in range(15):
        rows.append(
            {
                "transaction_id": f"VEL{i:04d}",
                "user_id": "USER001",
                "amount": 50 + (i % 6) * 15,
                "transaction_time": (burst_start + pd.Timedelta(seconds=i * 10)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": f"Rapid Merchant {i % 4}",
                "location": "Delhi",
                "payment_method": "Card",
            }
        )
    df = pd.DataFrame(rows)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    transactions = response.json()["transactions"]
    rapid = [row for row in transactions if str(row.get("transaction_id", "")).startswith("VEL")]
    assert len(rapid) == 15
    assert sum(float(row.get("fraud_score", 0)) > 30 for row in rapid) >= 3
    assert any("velocity" in transaction_text(row) for row in rapid)


async def test_large_amount_anomaly_detected():
    base = pd.Timestamp("2024-01-01 09:00:00")
    rows = []
    for i in range(30):
        rows.append(
            {
                "transaction_id": f"AMT{i:04d}",
                "user_id": "USER001",
                "amount": 200 + (i % 9) * 45,
                "transaction_time": (base + pd.Timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": f"Regular Shop {i % 4}",
                "location": "Mumbai",
                "payment_method": "UPI",
            }
        )
    rows.append(
        {
            "transaction_id": "AMT_EXTREME_95000",
            "user_id": "USER001",
            "amount": 95000,
            "transaction_time": (base + pd.Timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "merchant": "Luxury Electronics",
            "location": "Mumbai",
            "payment_method": "UPI",
        }
    )
    df = pd.DataFrame(rows)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    transactions = response.json()["transactions"]
    target = next(row for row in transactions if row.get("transaction_id") == "AMT_EXTREME_95000")
    assert float(target.get("fraud_score", 0)) > 40
    assert "amount" in transaction_text(target)


async def test_duplicate_payment_detected():
    base = pd.Timestamp("2024-01-01 09:00:00")
    rows = []
    for i in range(10):
        rows.append(
            {
                "transaction_id": f"DUPN{i:04d}",
                "user_id": f"USER{i + 10:03d}",
                "amount": 300 + i * 20,
                "transaction_time": (base + pd.Timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": f"Shop{i}",
                "location": "Pune",
                "payment_method": "Wallet",
            }
        )
    duplicate_start = pd.Timestamp("2024-01-03 15:00:00")
    for i in range(5):
        rows.append(
            {
                "transaction_id": f"DUPPAY{i:04d}",
                "user_id": "USER001",
                "amount": 1500,
                "transaction_time": (duplicate_start + pd.Timedelta(seconds=i * 30)).strftime("%Y-%m-%d %H:%M:%S"),
                "merchant": "ShopA",
                "location": "Delhi",
                "payment_method": "Card",
            }
        )
    df = pd.DataFrame(rows)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    transactions = response.json()["transactions"]
    duplicate_rows = [
        row
        for row in transactions
        if row.get("user_id") == "USER001" and row.get("merchant") == "ShopA" and float(row.get("amount", 0)) == 1500
    ]
    assert len(duplicate_rows) == 5
    assert any(float(row.get("fraud_score", 0)) > 0 for row in duplicate_rows)
    assert any("duplicate" in transaction_text(row) for row in duplicate_rows)


async def test_two_row_dataset():
    df = standard_df(2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 2


async def test_extra_columns():
    df = standard_df(30)[["transaction_id", "user_id", "amount", "transaction_time"]]
    for i in range(1, 51):
        df[f"col{i}"] = [f"extra_{i}_{j}" for j in range(len(df))]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert len(body["transactions"]) == 30


async def test_uppercase_column_names():
    df = standard_df(20)
    df.columns = [column.upper() for column in df.columns]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 20


async def test_whitespace_column_names():
    df = standard_df(20)[["transaction_id", "user_id", "amount", "transaction_time"]]
    df.columns = [" transaction_id ", " user_id ", " amount ", " transaction_time "]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 20


async def test_excel_file_upload():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"
    ws.append(["transaction_id", "user_id", "amount", "transaction_time", "merchant"])
    base = pd.Timestamp("2024-02-01 10:00:00")
    for i in range(30):
        ws.append(
            [
                f"XLSX{i:04d}",
                f"USER{i % 6:03d}",
                250 + (i % 10) * 75,
                (base + pd.Timedelta(minutes=i * 7)).strftime("%Y-%m-%d %H:%M:%S"),
                f"Excel Merchant {i % 4}",
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(
            client,
            buf.read(),
            filename="test.xlsx",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert len(body["transactions"]) == 30


async def test_unsupported_file_type():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, b"some random text data", filename="data.txt", content_type="text/plain")
    assert response.status_code != 500
    body = response.json()
    message = str(body.get("error") or body.get("message") or body.get("detail") or "")
    assert message
    assert "unsupported" in message.lower() or "format" in message.lower() or "file type" in message.lower()


async def test_download_fraud_csv():
    df = standard_df(50)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        upload_response = await upload_file(client, df_to_bytes(df))
        assert upload_response.status_code == 200, upload_response.text
        job_id = upload_response.json()["job_id"]
        response = await client.get(f"/api/download/fraud-transactions/{job_id}")
    assert response.status_code == 200, response.text
    content_type = response.headers.get("content-type", "").lower()
    assert "csv" in content_type or "octet-stream" in content_type
    assert response.content
    first_line = response.content.decode("utf-8", errors="replace").splitlines()[0]
    assert "," in first_line


async def test_download_all_scored_csv():
    df = standard_df(50)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        upload_response = await upload_file(client, df_to_bytes(df))
        assert upload_response.status_code == 200, upload_response.text
        job_id = upload_response.json()["job_id"]
        response = await client.get(f"/api/download/all-scored/{job_id}")
    assert response.status_code == 200, response.text
    parsed = pd.read_csv(io.BytesIO(response.content))
    assert len(parsed.index) == 50


async def test_download_pdf():
    df = standard_df(50)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        upload_response = await upload_file(client, df_to_bytes(df))
        assert upload_response.status_code == 200, upload_response.text
        job_id = upload_response.json()["job_id"]
        response = await client.get(f"/api/download/summary-report/{job_id}")
    assert response.status_code == 200, response.text
    assert "pdf" in response.headers.get("content-type", "").lower()
    assert response.content.startswith(b"%PDF")


async def test_invalid_job_id_download():
    missing_job_id = "this-job-does-not-exist-xyz123"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fraud_response = await client.get(f"/api/download/fraud-transactions/{missing_job_id}")
        all_scored_response = await client.get(f"/api/download/all-scored/{missing_job_id}")
        pdf_response = await client.get(f"/api/download/summary-report/{missing_job_id}")
    assert fraud_response.status_code == 404
    body = fraud_response.json()
    assert any(body.get(key) for key in ["detail", "error", "message"])
    assert all_scored_response.status_code == 404
    assert pdf_response.status_code == 404


async def test_mixed_currency_dataset():
    values = ["₹1,500", "$200", "INR 3000", "Rs. 750", "€500", "£300", "SGD 450", "AED 600", "1200.50", "Rs.900"]
    base = pd.Timestamp("2024-03-01 08:00:00")
    df = pd.DataFrame(
        {
            "transaction_id": [f"CURMIX{i:04d}" for i in range(30)],
            "user_id": [f"USER{i % 7:03d}" for i in range(30)],
            "amount": [values[i % len(values)] for i in range(30)],
            "transaction_time": [(base + pd.Timedelta(minutes=i * 3)).strftime("%Y-%m-%d %H:%M:%S") for i in range(30)],
            "merchant": [f"Currency Merchant {i % 5}" for i in range(30)],
            "location": [["Mumbai", "Dubai", "London", "Singapore"][i % 4] for i in range(30)],
            "payment_method": [["UPI", "Card", "Wallet"][i % 3] for i in range(30)],
        }
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    transactions = response.json()["transactions"]
    assert len(transactions) == 30
    assert all(isinstance(row.get("fraud_score"), (float, int)) for row in transactions)


async def test_large_dataset_performance():
    rows = 10000
    base = pd.Timestamp("2024-04-01 00:00:00")
    df = pd.DataFrame(
        {
            "transaction_id": [f"LARGE{i:05d}" for i in range(rows)],
            "user_id": [f"USER{i % 500:03d}" for i in range(rows)],
            "amount": [float(150 + (i % 100) * 11) for i in range(rows)],
            "transaction_time": [(base + pd.Timedelta(minutes=i * 2)).strftime("%Y-%m-%d %H:%M:%S") for i in range(rows)],
            "merchant": [f"Large Merchant {i % 80}" for i in range(rows)],
            "location": [["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai", "Dubai"][i % 6] for i in range(rows)],
            "payment_method": [["UPI", "Card", "Wallet", "Net Banking"][i % 4] for i in range(rows)],
        }
    )

    # 50 velocity-fraud rows: 10 rapid transactions for 5 users.
    for user_offset, user in enumerate(["USER901", "USER902", "USER903", "USER904", "USER905"]):
        start_index = user_offset * 10
        burst_start = pd.Timestamp("2024-05-01 12:00:00") + pd.Timedelta(hours=user_offset)
        for j in range(10):
            idx = start_index + j
            df.loc[idx, "transaction_id"] = f"VELBIG{user_offset}{j:02d}"
            df.loc[idx, "user_id"] = user
            df.loc[idx, "amount"] = float(50 + j * 5)
            df.loc[idx, "transaction_time"] = (burst_start + pd.Timedelta(seconds=j * 10)).strftime("%Y-%m-%d %H:%M:%S")
            df.loc[idx, "merchant"] = f"Rapid Merchant {j % 4}"
            df.loc[idx, "location"] = "Delhi"
            df.loc[idx, "payment_method"] = "Card"

    # 20 large amount anomaly rows.
    for j in range(20):
        idx = 200 + j
        df.loc[idx, "transaction_id"] = f"AMTBIG{j:03d}"
        df.loc[idx, "user_id"] = f"USER{j % 10:03d}"
        df.loc[idx, "amount"] = float(75000 + j * 2500)
        df.loc[idx, "transaction_time"] = (base + pd.Timedelta(days=30, minutes=j * 15)).strftime("%Y-%m-%d %H:%M:%S")
        df.loc[idx, "merchant"] = "High Value Electronics"
        df.loc[idx, "location"] = "Mumbai"
        df.loc[idx, "payment_method"] = "RTGS"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=120) as client:
        response = await upload_file(client, df_to_bytes(df))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    transactions = body["transactions"]
    assert len(transactions) == 10000
    assert all(0 <= float(row.get("fraud_score", -1)) <= 100 for row in transactions)
    assert any(row.get("risk_level") in {"High Risk", "Critical Risk"} for row in transactions)
