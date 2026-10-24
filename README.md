# WindSignal — UK Day-Ahead Wind Forecast Intelligence

An institutional-grade energy market analytics platform evaluating day-ahead wind generation forecast accuracy against actual outturn for wholesale electricity procurement in Great Britain.

---

## 1. System Overview

WindSignal integrates official Elexon BMRS data streams to empower renewable power trading desks with point-in-time forecast performance metrics across the January 2026 decision window ($D-1$) and delivery window ($D$).

- **Analytical Window:** Decision Dates: 2026-01-01 to 2026-01-31 | Delivery Window: 2026-01-02 00:00 UTC to 2026-02-01 23:00 UTC (744 hours, 100.0% complete).
- **Official Provenance:** Actuals from `/datasets/FUELHH/stream` (filtered to `WIND`); Forecasts from `/datasets/WINDFOR/stream`.
- **Temporal Alignment:** 30-minute constituent settlement periods aggregated into hourly arithmetic means to match 60-minute forecast horizons with zero temporal leakage.
- **Strict No-Look-Ahead Rule:** Point-in-time selection takes the latest forecast published at or before **09:20 UTC** on $D-1$ (EPEX SPOT GB day-ahead auction gate closure, analytical assumption).

---

## 2. Audited Metric Benchmarks

Across all 744 evaluated hourly delivery intervals, the verified benchmark metrics are:

| Metric | Value | Formulation / Interpretation |
|---|---|---|
| **Coverage** | 100.0% | 744 / 744 delivery intervals evaluated ($1{,}488$ constituent SPs) |
| **Mean Actual Outturn** | 11,283.56 MW | Arithmetic mean of verified national wind generation |
| **MAE** | 2,038.91 MW | Mean Absolute Error |
| **RMSE** | 2,504.76 MW | Root Mean Square Error |
| **Mean Bias Error (MBE)** | +1,747.89 MW | Systematic Overforecast ($\text{Error} = \text{Forecast} - \text{Actual}$) |
| **Normalized MAE (NMAE)** | 18.07% | $\text{MAE} / \text{Mean Actual} \times 100\%$ |
| **P90 Absolute Error** | 4,097.90 MW | 90th percentile of absolute error (Type 7 linear quantile interpolation) |
| **Max Overforecast** | +6,870.00 MW | Maximum positive volume error |
| **Max Underforecast** | -3,550.00 MW | Maximum negative volume error |

---

## 3. Technology Stack

- **Backend:** FastAPI, Pydantic v2, Pandas, NumPy, PyArrow, Uvicorn.
- **Frontend:** React 18, TypeScript, Vite, Recharts, Lucide React, Custom Responsive CSS.
- **Testing:** Pytest (31 tests), Vitest (6 tests), Endpoint contract verifier.

---

## 4. Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+ (Node 20+ recommended)

### 1. Start the Backend API
```bash
# In the repository root
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start FastAPI server on port 8000
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/health`

### 2. Start the React Frontend
```bash
# In the frontend directory
cd frontend
npm install
npm run dev
```
- Frontend Application: `http://localhost:5173`
- The Vite dev server automatically proxies requests matching `/api/*` to `http://localhost:8000`.

---

## 5. Docker Orchestration

Run both backend and frontend simultaneously via Docker Compose:

```bash
docker compose up --build
```
- Backend container listens on port `8000`.
- Frontend container listens on port `5173`.

Alternatively, build and run the multi-stage production Docker image:
```bash
docker build -t windsignal:latest .
docker run -p 8000:8000 windsignal:latest
```

---

## 6. Vercel Two-Project Production Deployment Guide

Deploying WindSignal on Vercel uses **two separate Vercel projects** connected to the same GitHub repository:
- **Project 1: Backend API** (FastAPI Python Serverless Runtime at root `.`)
- **Project 2: Frontend Dashboard** (React + TypeScript + Vite SPA in `frontend/`)

```
GitHub Repository: VaishnavSreekumar/WindSignal
   │
   ├── Project 1 (Root: .) ───────► Vercel Python Serverless ──► https://windsignal-api.vercel.app
   │                                  ├── pyproject.toml [tool.vercel] entrypoint = "src.api:app"
   │                                  ├── vercel.json (bundles data/**, rewrites to /src/api.py)
   │                                  └── All 7 /api/* endpoints + /docs
   │
   └── Project 2 (Root: frontend) ► Vercel Vite Frontend ─────► https://windsignal.vercel.app
                                      ├── frontend/vercel.json (SPA catch-all to index.html)
                                      └── VITE_API_BASE_URL = https://windsignal-api.vercel.app
```

---

### Step 1: Deploy the Backend API (`windsignal-api`)

1. In the [Vercel Dashboard](https://vercel.com/new), select **Add New Project** and import `VaishnavSreekumar/WindSignal`.
2. Configure Project Settings:
   - **Project Name:** `windsignal-api` (or your preferred name)
   - **Root Directory:** `./` (repository root)
   - **Framework Preset:** `Other`
   - **Build Command:** *(leave empty)*
   - **Output Directory:** *(leave empty)*
3. Environment Variables:
   - `CORS_ORIGINS`: `https://your-frontend.vercel.app,http://localhost:5173` *(Optional: when running on Vercel, requests from any `https://*.vercel.app` domain are permitted automatically).*
4. Click **Deploy**.
5. Once deployed, verify:
   - Health check: `https://<your-backend>.vercel.app/api/health`
   - Overview metrics: `https://<your-backend>.vercel.app/api/overview`
   - Interactive Swagger docs: `https://<your-backend>.vercel.app/docs`

---

### Step 2: Deploy the Frontend Dashboard (`windsignal`)

1. In the Vercel Dashboard, select **Add New Project** and import the same repository `VaishnavSreekumar/WindSignal`.
2. Configure Project Settings:
   - **Project Name:** `windsignal`
   - **Root Directory:** Click **Edit** and select `frontend`.
   - **Framework Preset:** `Vite` (automatically detected)
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Environment Variables:
   - `VITE_API_BASE_URL`: The production URL from Step 1, e.g. `https://<your-backend>.vercel.app` *(without trailing slash)*.
4. Click **Deploy**.
5. The frontend will build and serve with client-side SPA routing governed by `frontend/vercel.json`.

---

### Alternative: Heroku & Container Deployment
- **Heroku:** A compliant `Procfile` (`web: uvicorn src.api:app --host 0.0.0.0 --port $PORT`) is committed for single-dyno Python deployment.
- **Docker Compose:** Run both locally with `docker compose up --build`.

---

## 7. Testing & Verification

Run the full automated test suite:

```bash
# Python Backend Test Suite (31 passed)
pytest -v tests/

# Frontend Unit & Contract Tests (6 passed)
cd frontend && npm test

# Frontend TypeScript & Rollup Build
cd frontend && npm run build

# Direct API Contract Verification
python scripts/verify_frontend_endpoints.py
```

---

## 8. Methodology & Operational Limitations

1. **Analytical Decision Cutoff (09:20 UTC):**
   - The decision gate of 09:20 UTC corresponds to the order book gate closure for the Great Britain EPEX SPOT Day-Ahead 60-Minute wholesale auction.
   - NGESO's 07:30 UTC publication run is the latest WINDFOR run available prior to this gate.
   - Applicability to any specific utility's contractual or internal dispatch workflow is an **analytical assumption** and is transparently noted in the interface.
2. **Constituent Generation Population:**
   - Elexon BMRS `FUELHH` captures transmission-system-connected and large distribution-connected generation BM Units with operational metering visible to the National Grid ESO control room. Embedded small-scale wind is accounted for as negative system demand rather than gross metered generation.
3. **Temporal Aggregation Convention:**
   - Hourly actual generation is computed as the arithmetic mean of constituent settlement periods: $\text{Actual}(H) = (\text{SP}_{2H+1} + \text{SP}_{2H+2}) / 2$. This strictly reflects physical energy volume across the delivery hour without temporal lead or lag.

---

## 9. AI Tools Used & Development Governance

- **AI Assistance:** Developed with **Antigravity (Google DeepMind Advanced Agentic Coding)**.
- **Engineering Governance:**
  - Automated test-driven verification across all layers (31 Python backend tests, 6 Vitest frontend tests).
  - Independent analytical auditing (Phase 1.1 and Phase 3.1) of all intermediate matrices, schemas, and metric definitions.
  - Zero synthetic mock fallback policy: all UI charts and KPIs bind directly to live REST endpoints.
  - Strict mathematical invariance verification ensuring zero look-ahead bias and sign convention adherence ($\text{Error} = \text{Forecast} - \text{Actual}$).

