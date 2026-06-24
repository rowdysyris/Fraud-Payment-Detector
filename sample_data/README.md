# SentinelPay AI Sample Data

This folder contains deterministic demo datasets for testing SentinelPay AI from the frontend upload screen or through the backend API.

## Files

### `standard_transactions.csv`

Clean transaction data with the standard schema:

```text
transaction_id,user_id,transaction_time,amount,merchant,location,payment_method,status,currency
```

It contains 200+ rows with normal and suspicious transactions. Expected fraud patterns include amount anomalies, rapid same-user activity, duplicate payment clusters, risky merchant concentration, zero amounts, refund-like negative amounts, and extreme transaction amounts.

### `messy_transactions.csv`

Messy imported payment data with non-standard column names such as `Txn ID`, `CUSTOMER!!!`, `Payment Date/Time`, `Txn Amt ₹`, and `Shop Name!!!`.

It tests schema mapping and cleaning for `₹`, `Rs.`, `INR`, `$`, comma-formatted amounts, mixed date formats, duplicate rows, duplicate transaction IDs, emoji/special characters, long merchant names, and missing optional-style values.

### `edge_case_transactions.csv`

Malformed and unusual transaction data for robustness checks.

It includes invalid amount strings, blank values, zero amounts, negative/refund amounts, extremely large amounts, mixed currencies, rapid transaction bursts, repeated same-user payments, duplicate transaction IDs, duplicate payment signatures, and many locations in a short time.

## Regenerate datasets

From the project root:

```bash
cd sample_data
python generate_sample_data.py
```

The script uses fixed seeds, so the generated CSV files are reproducible.

## Upload through the UI

1. Start the backend:

```bash
cd backend
uvicorn app.main:app --reload
```

2. Start the frontend:

```bash
cd frontend
npm run dev
```

3. Open `http://localhost:5173`.
4. Upload one of the CSV files from this folder.
5. Review the dashboard, risk funnel, agent findings, flagged transactions, and downloads.

## Upload through the API

From the project root while the backend is running:

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -F "file=@sample_data/standard_transactions.csv"
```

## Expected behavior

The exact fraud scores can change if the agent logic changes, but these datasets should consistently produce Low, Medium, High, and Critical risk examples. The app should either process a dataset successfully or return a clear validation message without crashing.

SentinelPay AI flags suspicious activity for review and does not prove legal fraud.
