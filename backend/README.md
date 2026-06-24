# SentinelPay AI Backend

FastAPI backend for SentinelPay AI, an Agentic Fraud Payment Investigator.

## Run locally

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

## Health check

```bash
curl http://localhost:8000/health
```

## API endpoints

```text
GET  /health
POST /api/analyze
GET  /api/download/fraud-transactions/{job_id}
GET  /api/download/all-scored/{job_id}
GET  /api/download/summary-report/{job_id}
```

## Tests

```bash
cd backend
pytest
```

## Runtime storage

Generated reports are written to `backend/storage/{job_id}/` during runtime. Git ignores these job folders and keeps only `backend/storage/.gitkeep`.
