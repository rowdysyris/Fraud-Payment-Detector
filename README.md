# SentinelPay AI

SentinelPay AI is a full-stack **Agentic Fraud Payment Investigator** that analyzes uploaded transaction datasets and produces explainable fraud-risk scores with downloadable CSV/PDF reports.

## Live Demo

Frontend: https://fraud-payment-detector.vercel.app  
Backend Health Check: https://sentinelpay-ai-backend.onrender.com/health

## Access

No login is required. Open the live demo and upload a transaction CSV/XLSX file.

## Problem statement

Payment and finance teams often receive messy CSV or Excel transaction exports with inconsistent column names, mixed amount formats, invalid dates, duplicates, missing values, and suspicious behavior hidden across users, merchants, locations, and timestamps. SentinelPay AI turns those files into a structured fraud-investigation workflow: validate, map, clean, detect, score, explain, recommend, and export.

## Features

- CSV, XLS, and XLSX upload support
- Messy schema mapping for real-world transaction exports
- Defensive validation with readable error responses
- Amount cleaning for symbols and text such as `₹`, `Rs.`, `INR`, `$`, `€`, commas, blanks, and invalid strings
- Safe mixed-date parsing
- Duplicate row and duplicate transaction ID detection
- Rule-based fraud detection agents
- Lightweight RandomForest ML fraud probability layer trained from rule-generated labels
- Hybrid final fraud score from 0 to 100
- Risk levels: Low Risk, Medium Risk, High Risk, Critical Risk
- Per-transaction reason, pattern, confidence, review status, and recommended action
- Downloadable fraud CSV, all-scored CSV, and manager-friendly PDF report
- React dashboard with upload flow, 3D risk funnel, KPI cards, charts, clickable flagged transaction table, deep-dive investigation modal, and report buttons
- Backend pytest suite covering normal, messy, file-format, download, performance, and edge-case inputs
- Deterministic sample datasets for demos

## Tech stack

### Backend

- Python
- FastAPI
- Pandas
- NumPy
- Scikit-learn
- Joblib
- ReportLab
- OpenPyXL
- pytest
- httpx

### Frontend

- React
- Vite
- Tailwind CSS
- Framer Motion
- React Three Fiber / Drei
- Recharts
- Axios

## Fraud agents

- Data Validation Agent
- Schema Mapping Agent
- Data Cleaning Agent
- Amount Anomaly Agent
- Velocity Fraud Agent
- User Behavior Agent
- Merchant Risk Agent
- Location Risk Agent
- Duplicate Payment Agent
- Final Risk Scoring Agent
- Recommendation Agent

## Backend API endpoints

```text
GET  /health
POST /api/analyze
GET  /api/download/fraud-transactions/{job_id}
GET  /api/download/all-scored/{job_id}
GET  /api/download/summary-report/{job_id}
GET  /api/transaction-detail/{job_id}/{transaction_id}
PATCH /api/transaction-review/{job_id}/{transaction_id}
```

## Transaction deep-dive modal

Click any flagged transaction row in the dashboard to open a real investigation view loaded from the backend job storage. The modal shows:

- Full transaction details
- Recent same-user transaction timeline
- Agent-by-agent score contribution and reason
- Deterministic AI-style fraud explanation
- Review actions: Reviewed, Confirmed Fraud, Marked Safe

Review actions update `backend/storage/{job_id}/all_transactions_with_fraud_scores.csv` and `fraud_transactions.csv` when the transaction appears in both files.

## Final output files

Each successful analysis creates runtime files under `backend/storage/{job_id}/`:

```text
fraud_transactions.csv
all_transactions_with_fraud_scores.csv
fraud_summary_report.pdf
```

These runtime files are ignored by Git. Only `backend/storage/.gitkeep` is committed.

## Folder structure

```text
sentinelpay-ai/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── schemas.py
│   │   ├── api/
│   │   ├── agents/
│   │   ├── core/
│   │   ├── services/
│   │   ├── utils/
│   │   └── ml/
│   ├── tests/
│   ├── storage/
│   │   └── .gitkeep
│   ├── requirements.txt
│   ├── pytest.ini
│   └── README.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── src/
│   └── README.md
├── sample_data/
│   ├── generate_sample_data.py
│   ├── standard_transactions.csv
│   ├── messy_transactions.csv
│   ├── edge_case_transactions.csv
│   └── README.md
├── .env.example
├── .gitignore
└── README.md
```

## Setup instructions

Clone the repository, then copy the environment example if needed:

```bash
cp .env.example .env
```

For local development, the frontend defaults to:

```text
VITE_API_BASE_URL=http://localhost:8000
```

## Backend run instructions

Windows:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Mac/Linux:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok","service":"SentinelPay AI","version":"0.5.0"}
```

## Frontend run instructions

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Test instructions

```bash
cd backend
pytest
```

The focused suites can also be run directly:

```bash
pytest tests/test_pipeline.py
pytest tests/test_edge_cases.py
pytest tests/test_ml_inference.py
pytest tests/test_ml_full_integration.py
```

## Train ML model

Train the lightweight RandomForest fraud model from rule-generated labels:

```bash
cd backend
python -m app.ml.train_model
```

Or train with a custom CSV or Excel file:

```bash
cd backend
python -m app.ml.train_model --input ../sample_data/standard_transactions.csv
```

The ML layer is trained using the existing rule-based fraud score as weak supervision:

```text
fraud_label = 1 if rule_fraud_score >= 61 else 0
```

This is a lightweight supervised layer. It improves scoring by adding `ml_fraud_probability`, but it does not replace the rule-based explainability. The final score combines 70% rule-based score and 30% ML probability when a trained model exists. If the model file is missing, corrupted, or metadata is unavailable, the system returns a safe numeric ML probability, continues to work from the rule-based score, and still generates reports.

`confidence` is a demo-friendly score indicator derived from `fraud_score / 100`; it should not be described as a calibrated statistical probability. The bundled model is not trained on real bank-confirmed fraud labels unless a real labeled dataset is later provided.

## Sample data instructions

The `sample_data/` folder contains deterministic demo datasets:

```text
standard_transactions.csv      Clean standard schema with normal and suspicious transactions
messy_transactions.csv         Messy column names, mixed amount/date formats, duplicates, weird text
edge_case_transactions.csv     Invalid values, zero/negative amounts, missing values, rapid bursts, location anomalies
```

Regenerate them:

```bash
cd sample_data
python generate_sample_data.py
```

Upload a sample through the API:

```bash
curl -X POST "http://localhost:8000/api/analyze" \
  -F "file=@sample_data/standard_transactions.csv"
```

## Edge cases handled

- Empty CSV
- Header-only CSV
- Missing amount column
- Missing user ID column
- Missing transaction time column
- One-row and two-row datasets
- All amount values missing
- All transaction times missing
- Invalid amount strings
- `₹`, `Rs.`, `INR`, `$`, `€`, comma-separated, and spaced amounts
- Negative amounts and refund-like rows
- Zero amounts
- Extremely large amounts
- Mixed date formats and invalid dates
- Duplicate rows
- Duplicate transaction IDs
- Same user repeated quickly
- Many merchants in a short time
- Many locations in a short time
- Unicode merchant names
- Special characters in IDs and merchant names
- UTF-8 BOM CSV files
- 100+ irrelevant columns
- Missing optional columns
- Large in-memory dataset performance tests

## Disclaimer

This system flags suspicious transactions for review. It does not prove legal fraud.

## Limitations

- The ML model is trained from rule-generated labels, not real bank-confirmed fraud labels.
- The system flags suspicious transactions for review; it does not prove legal fraud.
- Render Free backend may sleep after inactivity.
- File-based job storage is used for demo simplicity; production systems should use persistent storage such as PostgreSQL/S3.
- No authentication is included because this is a portfolio/demo project.

## Future Improvements

- Add PostgreSQL for persistent investigation history.
- Add user authentication and role-based access.
- Add cloud file storage for generated reports.
- Train the ML model on real labeled fraud datasets.
- Add SHAP-based model explainability.
- Add Kafka-based real-time transaction streaming.
- Add Docker Compose for local full-stack setup.

## Project 2-minute explanation

SentinelPay AI is a full-stack fraud investigation platform for messy transaction datasets. I built a FastAPI backend that accepts CSV or Excel files, maps messy column names into a standard transaction schema, cleans difficult values like currency strings and mixed dates, validates the dataset, and then runs multiple explainable fraud agents.

The agents detect amount anomalies, velocity fraud, unusual user behavior, merchant risk, location anomalies, and duplicate payments. A lightweight RandomForest model can then add an ML fraud probability trained from rule-generated labels. The final score combines explainable rule signals with ML probability when a trained model exists. Every transaction gets a rule fraud score, ML fraud probability, final fraud score, risk level, fraud pattern, fraud reason, triggered agents, confidence, review status, and recommended action.

The frontend is built with React, Vite, Tailwind, Framer Motion, React Three Fiber, and Recharts. It provides a premium dashboard with drag-and-drop upload, a 3D risk funnel, KPI cards, charts, a clickable flagged transactions table, a transaction deep-dive modal with user timeline and agent breakdown, clean validation errors, and download buttons for CSV and PDF reports.

The project is tested heavily with pytest. The tests cover clean data, messy schemas, file uploads, Excel support, downloads, large datasets, invalid values, duplicate rows, special characters, Unicode, missing optional columns, and edge cases where the app must never crash with a raw server error.
