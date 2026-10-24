# WindSignal — Phase 3: React Frontend Engineering Report

**Product:** WindSignal — UK Day-Ahead Wind Forecast Intelligence  
**Target User:** Electricity Procurement Desk / Day-Ahead Trading Desk (UK Market)  
**Date:** October 2026  
**Status:** Complete & Verified  

---

## 1. Executive Summary

Phase 3 delivers a production-grade, responsive React + TypeScript frontend for **WindSignal**, interfacing directly with the validated Phase 2 FastAPI backend and Phase 1/1.1 Elexon historical pipeline (`FUELHH` and `WINDFOR`).

The interface provides commercial energy analysts and traders with an intuitive yet mathematically rigorous decision cockpit to evaluate day-ahead wind generation forecasts against outturn across January 2026. Every metric, chart, and vintage is tied directly to real backend API contracts without mocked fallbacks, fabricated records, or look-ahead leakage.

---

## 2. Technical Stack & Architecture

| Layer | Technology | Rationale & Configuration |
|---|---|---|
| **Frontend Framework** | React 18 + TypeScript | Strict typing aligned with backend Pydantic schemas; type-safe contract enforcement. |
| **Build Tooling** | Vite 5 | Fast HMR in development, optimized rollup bundling in production (`dist/`). |
| **Data Visualization** | Recharts 2 | Responsive SVG charting: dual-line forecast vs actual with error area, vintage scatter, bar charts. |
| **Icons & Design** | Lucide React + Custom CSS | Energy-market dark navy terminal palette (`#0a0f1d`, `#162038`, `#38bdf8`, `#10b981`, `#f59e0b`). |
| **API Client** | Native Fetch (`frontend/src/services/api.ts`) | Clean isomorphic HTTP client with explicit `ApiError` handling and parameter serialization. |
| **Testing** | Vitest + Pytest | 5 frontend contract & transformation tests + 30 backend tests across FastAPI and analytical pipeline. |

---

## 3. Four Core Screens

### Screen 1: Decision Cockpit
- **Interactive Time-Series Chart:** Visualizes hourly Day-Ahead Forecast MW vs Actual Outturn MW across the complete 744-hour January 2026 delivery window.
- **Signed Forecast Error:** Visualized directly on the chart and tooltips, adhering strictly to:
  $$\text{Error} = \text{Forecast MW} - \text{Actual Outturn MW}$$
  Positive error indicates wind overforecasting; negative error indicates underforecasting.
- **Dynamic KPI Scorecard:** Displays MAE (2,038.91 MW), RMSE (2,504.76 MW), Mean Bias (+1,747.89 MW), Normalized MAE (18.07%), P90 Absolute Error (4,097.90 MW), and Delivery Interval Coverage (100.0%).
- **Date-Range Filtering:** Quick range presets (Full Window, First 10 Days, Mid January, Final Week) and native HTML5 date pickers that dynamically query `/api/forecast-vs-actual` and `/api/accuracy`.
- **Operational Assumptions:** Explicit banner detailing the January 2026 decision window, corresponding delivery window (2026-01-02 to 2026-02-01), and the **09:20 UTC cutoff** explicitly labeled as an analytical assumption based on EPEX SPOT GB day-ahead order book closure.
- **Robust System States:** Polished visual states for Loading, Empty filtered ranges, and API Error banners with retry capability.

### Screen 2: Forecast Vintage Explorer
- **Delivery Interval Selector:** Allows traders to pick any of the 744 delivery hours (or jump directly to peak generation or highest error intervals).
- **Publication Scatter Chart:** Plots every historical publication run (`publishTime` vs forecast MW) targeting that exact delivery hour.
- **Eligibility Distinction:**
  - **Eligible Vintages (Pre-Cutoff):** Highlighted with green badges and markers, published at or before 09:20 UTC on $D-1$.
  - **Excluded Vintages (Post-Cutoff):** Subdued with amber/red warnings, clearly marked as unavailable at auction gate closure to avoid look-ahead bias.
  - **Selected Vintage:** Highlighted with a special star badge and border, showing the exact run chosen by the deterministic decision rule (e.g., NGESO 07:30 UTC run).
- **Forecast Lead Time:** Displays true operational lead time in hours from publication to delivery start.
- **Empty State Honesty:** If no publications exist for a hypothetical timestamp, clearly explains that rather than fabricating points.

### Screen 3: Accuracy Analysis
- **Daily Performance Trends:** Synchronized bar/line chart displaying daily MAE and daily Mean Bias across all 31 delivery days.
- **Error Distribution Histogram:** Binned distribution of forecast errors (from $<-3{,}000\text{ MW}$ underforecast to $>+5{,}000\text{ MW}$ extreme overforecast) based directly on API observations.
- **Procurement & Imbalance Impact Commentary:** Honest qualitative analysis explaining that the +1,747.89 MW average overforecast pushed market participants into short positions in the balancing mechanism, incurring cashout exposure. Completely avoids unsubstantiated cost-savings claims.

### Screen 4: Data Quality & Methodology
- **Automated Validation Invariant Ledger:** Direct tabular presentation from `/api/data-quality`:
  - Zero look-ahead violations ($0 / 744$).
  - 100.0% delivery window coverage ($744 / 744$ hours).
  - Key uniqueness ($0$ duplicate timestamps).
  - 1,488 verified constituent settlement periods ($31 \times 48$).
- **Methodology Documentation Cards:**
  1. *Temporal Interval Alignment:* Explains arithmetic mean calculation of odd ($2H+1$) and even ($2H+2$) half-hourly periods to aggregate 30m `FUELHH` into 60m `WINDFOR` intervals.
  2. *Point-in-Time Vintage Selection:* Explains the 09:20 UTC cutoff on $D-1$ and tie-breaking deterministic rules.
  3. *Error Convention Formulations:* Clear equations for MAE, RMSE, MBE, and NMAE.
  4. *Elexon Stream API Provenance:* Details the `/datasets/FUELHH/stream` and `/datasets/WINDFOR/stream` endpoints and latency benchmarks.
- **One-Click CSV Export:** Direct API trigger for downloading `/api/export.csv` with optional date bounds.

---

## 4. API Verification Matrix

Every frontend endpoint was verified against the real FastAPI backend using `scripts/verify_frontend_endpoints.py`:

| HTTP Method & Endpoint | Frontend API Method | Contract Status | Response Summary |
|---|---|---|---|
| `GET /api/health` | `api.getHealth()` | Verified (200 OK) | `{status: "ok", dataset_ready: true, evaluated_rows: 744, ...}` |
| `GET /api/overview` | `api.getOverview()` | Verified (200 OK) | Full-window headline KPIs, decision window, and cutoff details |
| `GET /api/forecast-vs-actual` | `api.getForecastVsActual()` | Verified (200 OK) | 744 hourly records with forecast, actual, error, and lead times |
| `GET /api/forecast-vs-actual?delivery_date_from=...` | `api.getForecastVsActual(from, to)` | Verified (200 OK) | Correctly sliced dataset for selected date boundaries |
| `GET /api/accuracy` | `api.getAccuracy(from, to)` | Verified (200 OK) | Recalculated MAE, RMSE, MBE, NMAE, and P90 error |
| `GET /api/forecast-vintages?delivery_start_time=...` | `api.getForecastVintages(time)` | Verified (200 OK) | Full vintage array with `is_eligible` and `is_selected` |
| `GET /api/data-quality` | `api.getDataQuality()` | Verified (200 OK) | Invariants, audit counts, and raw ingestion latencies |
| `GET /api/export.csv` | `api.getExportCsvUrl(from, to)` | Verified (200 OK) | Streaming CSV download (`Content-Type: text/csv`, 81,574 bytes) |

---

## 5. Verification & Test Execution Results

### Frontend Unit & Contract Tests (`npm test`):
```text
 ✓ src/tests/api.test.ts (5 tests) 3ms
 Test Files  1 passed (1)
      Tests  5 passed (5)
   Duration  130ms
```

### Frontend TypeScript & Production Build (`npm run build`):
```text
> frontend@0.0.0 build
> tsc && vite build

vite v8.3.5 building client environment for production...
transforming...
✓ 2513 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   1.07 kB │ gzip:   0.61 kB
dist/assets/index-DDlyDM9Y.css    9.10 kB │ gzip:   2.38 kB
dist/assets/index-CAKMB60e.js   656.73 kB │ gzip: 192.05 kB
✓ built in 457ms
```

### Backend Test Suite (`pytest -v tests/`):
```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
collected 30 items

tests/test_api.py::test_health_endpoint PASSED                           [  3%]
tests/test_api.py::test_overview_endpoint_metrics_consistency PASSED     [  6%]
tests/test_api.py::test_forecast_vs_actual_full_window PASSED            [ 10%]
tests/test_api.py::test_forecast_vs_actual_date_filtering PASSED         [ 13%]
tests/test_api.py::test_forecast_vs_actual_empty_filter_result PASSED    [ 16%]
tests/test_api.py::test_forecast_vs_actual_invalid_date_range PASSED     [ 20%]
tests/test_api.py::test_accuracy_metrics_full_window PASSED              [ 23%]
tests/test_api.py::test_accuracy_metrics_filtered_recalculation PASSED   [ 26%]
tests/test_api.py::test_accuracy_metrics_empty_window PASSED             [ 30%]
tests/test_api.py::test_forecast_vintages_valid_interval PASSED          [ 33%]
tests/test_api.py::test_forecast_vintages_invalid_timestamp PASSED       [ 36%]
tests/test_api.py::test_forecast_vintages_not_found PASSED               [ 40%]
tests/test_api.py::test_data_quality_endpoint PASSED                     [ 43%]
tests/test_api.py::test_csv_export_endpoint PASSED                       [ 46%]
tests/test_api.py::test_csv_export_filtered PASSED                       [ 50%]
tests/test_api.py::test_cors_headers PASSED                              [ 53%]
tests/test_pipeline.py::test_timestamp_utc_normalization PASSED          [ 56%]
tests/test_pipeline.py::test_date_boundaries_and_coverage PASSED         [ 60%]
tests/test_pipeline.py::test_no_look_ahead_bias_invariant PASSED         [ 63%]
tests/test_pipeline.py::test_deterministic_vintage_selection_logic PASSED [ 66%]
tests/test_pipeline.py::test_hourly_vs_half_hourly_aggregation PASSED    [ 70%]
tests/test_pipeline.py::test_production_hourly_period_count_integrity PASSED [ 73%]
tests/test_pipeline.py::test_duplicates_in_analytical_dataset PASSED     [ 76%]
tests/test_pipeline.py::test_no_missing_intervals_in_delivery_window PASSED [ 80%]
tests/test_pipeline.py::test_generation_values_sanity PASSED             [ 83%]
tests/test_pipeline.py::test_configurable_decision_cutoff_behavior PASSED [ 86%]
tests/test_pipeline.py::test_forecast_error_sign_convention PASSED       [ 90%]
tests/test_pipeline.py::test_single_period_missing_sp2_handling PASSED   [ 93%]
tests/test_pipeline.py::test_vintage_selection_fallback_when_0730_missing PASSED [ 96%]
tests/test_pipeline.py::test_vintage_selection_deterministic_tie_breaking PASSED [100%]

============================= 30 passed in 9.94s ==============================
```

---

## 6. Deployment & Docker Architecture

### Heroku Deployment (Recommended for Unified Python Backend + Container Registry)
- **Configuration:** A root-level `Procfile` is provided:
  ```text
  web: uvicorn src.api:app --host 0.0.0.0 --port $PORT
  ```
- **Container Registry Option:** The multi-stage `Dockerfile` packages the application with Python 3.11, precomputes frontend artifacts, and serves via Uvicorn.
- **Heroku Constraints:** Ephemeral filesystem requires committing `data/processed/` Parquet files (already committed in git).

### Vercel Deployment (Recommended for React SPA Frontend)
- **Configuration:** `frontend/vercel.json` provides client-side SPA routing rewrites to `/index.html`.
- **Environment:** In the Vercel project settings, set `VITE_API_BASE_URL` to point to the deployed FastAPI service URL (e.g. `https://windsignal-backend.herokuapp.com`).
- **Limitation:** Vercel is a serverless frontend platform; long-running Python data services or stateful Parquet querying are best decoupled to Heroku, Render, or a container host.

### Local Container Orchestration (`docker-compose.yml`)
- Provides synchronized execution of both services locally:
  - `backend`: FastAPI on port `8000`.
  - `frontend`: Vite dev server with live reload on port `5173`.

---

## 7. Local Startup Commands & Environment Variables

### Backend Startup (Python 3.11+)
```bash
# In repository root:
pip install -r requirements.txt
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```
*Backend URL:* `http://localhost:8000` (API docs at `/docs`)

### Frontend Startup (Node 18+)
```bash
# In frontend/ directory:
cd frontend
npm install
npm run dev
```
*Frontend URL:* `http://localhost:5173` (proxies `/api` requests to `http://localhost:8000` automatically)

### Environment Variables
- `VITE_API_BASE_URL`: Base URL for the FastAPI backend (e.g., `http://localhost:8000` or empty to use Vite proxy).
- `CORS_ORIGINS`: Comma-delimited allowed origins for FastAPI (defaults to `http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173`).
- `PORT`: HTTP port for backend service (default: `8000`).

---

## 8. Summary of Files Created or Modified in Phase 3

### Created Files:
1. `frontend/package.json` — Vite, React, TypeScript, Recharts, Lucide, Vitest dependencies.
2. `frontend/vite.config.ts` — Vite config with local `/api` proxy to `http://localhost:8000`.
3. `frontend/tsconfig.json` & `frontend/tsconfig.node.json` — TypeScript configuration.
4. `frontend/index.html` — HTML shell with Inter typography and meta tags.
5. `frontend/src/types/api.ts` — TypeScript type definitions mirroring backend Pydantic schemas.
6. `frontend/src/services/api.ts` — Type-safe HTTP client with error handling.
7. `frontend/src/styles/theme.css` — Energy trading dark navy aesthetic and responsive styles.
8. `frontend/src/components/Header.tsx` — Terminal navigation bar, status pill, and window summary.
9. `frontend/src/components/KPICard.tsx` — Modular KPI metric card with sub-metrics and tooltip.
10. `frontend/src/components/CockpitView.tsx` — Screen 1: Forecast vs Actual chart and KPI grid.
11. `frontend/src/components/VintageExplorerView.tsx` — Screen 2: Forecast Vintage Explorer.
12. `frontend/src/components/AccuracyAnalysisView.tsx` — Screen 3: Daily accuracy trends & error distribution.
13. `frontend/src/components/DataQualityView.tsx` — Screen 4: Invariants, methodology cards, and CSV export.
14. `frontend/src/App.tsx` — Main application shell with tab routing, date filter state, and global error handling.
15. `frontend/src/main.tsx` — React application entry point.
16. `frontend/src/tests/api.test.ts` — Vitest unit tests for client and transformations.
17. `frontend/vercel.json` — Vercel SPA rewrite routing config.
18. `frontend/.env.example` — Example frontend environment configuration.
19. `Dockerfile` — Multi-stage container build for frontend and FastAPI service.
20. `docker-compose.yml` — Local multi-container development configuration.
21. `Procfile` — Heroku web process specification.
22. `.env.example` — Root-level environment variable template.
23. `scripts/verify_frontend_endpoints.py` — Live contract validation script.
24. `docs/phase3_report.md` — This comprehensive Phase 3 report.

### Modified Files:
None in `src/` or `data/` — The analytical pipeline and backend contracts were strictly preserved without modification.

---

## 9. Known Limitations & Unresolved Issues

1. **Analytical Assumption on Cutoff:** The 09:20 UTC cutoff represents the EPEX SPOT GB day-ahead auction gate closure. NGESO's 07:30 UTC publication run is the latest run published prior to this cutoff. Should an energy utility operate on a different decision gate (e.g. Nord Pool 09:00 UTC or an internal desk cutoff of 08:30 UTC), this parameter can be configured in `src/services.py`, but it is currently static across the default API responses.
2. **Chart Chunk Size:** Due to Recharts SVG rendering bundle sizes, Vite emits a standard chunk warning (>500 kB). This can be split with `React.lazy()` if aggressive initial page load optimization is required.
3. **Decoupled Deployment Architecture:** As documented, Vercel hosts the static React bundle, while Heroku/Docker hosts the stateful FastAPI service reading the Parquet file.
