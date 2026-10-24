# WindSignal Data Quality & Ingestion Report

**Audit Generated:** 2026-10-24T07:29:01.176200+00:00  
**Target Decision Window:** 2026-01-01 to 2026-01-31  
**Target Delivery Window:** 2026-01-02T00:00:00+00:00 to 2026-02-01T23:00:00+00:00  
**Configured Decision Cutoff:** 09:20:00 UTC (EPEX SPOT GB 60-min Gate Closure)  

---

## 1. Executive Quality Summary

- **Delivery Coverage:** **744 / 744 hours (100.0%)**
- **Missing Delivery Hours:** **0**
- **Look-Ahead Bias Violations:** **0** (100% of used forecasts published strictly before cutoff)
- **Duplicate Records in Analytical Dataset:** **0**
- **Hourly Aggregation Period Integrity:** **PASSED (2 half-hours per delivery hour)**
- **Out-of-Bounds Generation Values (< 0 MW):** **0**

---

## 2. Ingestion Audit

### FUELHH (Actual Half-Hourly Outturn Generation)
- **Source Endpoint:** `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
- **Exact Query Parameters:** `{"settlementDateFrom": "2026-01-01", "settlementDateTo": "2026-02-02", "fuelType": "WIND"}`
- **HTTP Status Code:** `200`
- **Retrieval Timestamp:** `2026-10-24T07:19:44.343498+00:00`
- **Query Latency:** `1.66 seconds`
- **Total Records Ingested:** `1584`
- **Settlement Periods per Day:** 48
- **Raw Duplicates:** `0`

### WINDFOR (Historical Wind Generation Forecasts)
- **Source Endpoint:** `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
- **Exact Query Parameters:** `{"publishDateTimeFrom": "2025-12-30T00:00:00Z", "publishDateTimeTo": "2026-01-31T23:59:59Z"}`
- **HTTP Status Code:** `200`
- **Retrieval Timestamp:** `2026-10-24T07:19:46.015185+00:00`
- **Query Latency:** `3.43 seconds`
- **Total Records Ingested:** `19272`
- **Publication Batches per Day:** 8 runs (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC)
- **Raw Duplicates:** `0`

---

## 3. Analytical Validation Invariants

| Validation Test | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :---: |
| **Strict No-Look-Ahead Rule** | `publishTime <= cutoff_time` for all records | Max difference: 0 violations | **PASS** |
| **Delivery Date Boundaries** | 2026-01-02 00:00 UTC to 2026-02-01 23:00 UTC (744 hours) | Exactly 744 hours covered | **PASS** |
| **Temporal Resolution Alignment** | 2 settlement periods aggregated per hour | Integrity boolean: True | **PASS** |
| **Duplicate Keys `(delivery_start_time)`** | 0 duplicates | 0 duplicates | **PASS** |
| **Generation Feasibility** | Generation >= 0 MW, Generation <= 25,000 MW | Actual min: 0, Forecast min: 0 | **PASS** |

---

## 4. Benchmark Accuracy Metrics (January 2026 Delivery Window)

- **Mean Actual Wind Generation:** `11283.56 MW`
- **Mean Absolute Error (MAE):** `2038.91 MW`
- **Root Mean Squared Error (RMSE):** `2504.76 MW`
- **Normalized MAE (% of Mean Actual):** `18.07%`
- **Mean Bias Error (MBE):** `1747.89 MW` (Positive = Overforecasting tendency)
- **Peak Overforecast Error:** `+6870.0 MW`
- **Peak Underforecast Error:** `-3550.0 MW`

---

## 5. Machine-Readable Artifacts Generated

1. `data/processed/wind_analytical_dataset.parquet`
2. `data/processed/wind_analytical_dataset.csv`
3. `data/processed/data_quality_summary.json`
4. `data/raw/fuelhh_raw.json`
5. `data/raw/windfor_raw.json`
