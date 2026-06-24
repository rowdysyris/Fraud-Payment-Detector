# SentinelPay AI Frontend

React + Vite frontend for SentinelPay AI.

## Environment

The frontend reads the backend URL from:

```text
VITE_API_BASE_URL=http://localhost:8000
```

This value is provided in the root `.env.example`. Without an environment file, the frontend defaults to `http://localhost:8000`.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## Build

```bash
cd frontend
npm run build
```

## UI behavior

- Uploads CSV/XLS/XLSX files to `POST /api/analyze`.
- Shows loading state during analysis.
- Shows clean validation, server, and network errors.
- Does not display hardcoded dashboard numbers before a successful backend response.
- Renders summary cards, 3D risk funnel, charts, agent findings, flagged transactions, and report downloads from real backend data.
