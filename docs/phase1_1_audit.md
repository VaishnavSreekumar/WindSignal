# WindSignal Phase 1.1 — Independent Analytical Audit Report

**Audit Date:** 2026-10-24  
**Audit Target:** WindSignal Phase 1 Historical Data Pipeline  
**Auditor:** Antigravity Autonomous Systems Engineering & Verification Team  
**Workspace:** `windsignal`  

---

## 1. Executive Verdict

### **Overall Verdict: PASS**
The Phase 1 analytical foundation is **strictly sound, verified, and safe to use** for subsequent product and API development.

### Key Audit Findings:
1. **Mathematical Invariant Verified:** The forecast error convention is strictly confirmed as:
   $$\text{Error} = \text{Forecast} - \text{Actual}$$
   Overforecasts ($\text{Forecast} > \text{Actual}$) produce positive error values ($> 0$); underforecasts ($\text{Forecast} < \text{Actual}$) produce negative error values ($< 0$).
2. **Zero Look-Ahead Bias Verified:** For all 744 evaluated delivery hours, the selected forecast vintage was timestamped at or prior to the decision cutoff ($P \le C$). Every evaluated forecast was published strictly before delivery began ($P < T_{del}$, mean lead time 28.0 hours).
3. **Temporal Interval Pairing Verified:** All 744 hourly delivery intervals are paired with exactly two constituent half-hourly settlement periods ($SP_{start}$ odd, $SP_{end} = SP_{start} + 1$). The arithmetic mean is verified to exact floating-point precision.
4. **Boundary Completeness Verified:** The delivery window spans from `2026-01-02 00:00:00Z` through `2026-02-01 23:00:00Z` (exactly 744 hourly intervals derived from 1,488 constituent half-hourly settlement observations). Missing intervals: 0. Duplicates: 0.
5. **Defect Found & Remediated:** A subtle aggregation bug in `aggregate_fuelhh_to_hourly`—where an isolated missing half-hour ($SP_2$) would duplicate $SP_1$ into $SP_2$—was identified, corrected to yield `NaN`, and regression-tested. In the production January 2026 dataset, all 1,488 half-hours are complete, so this defect did not corrupt the benchmark metrics.

---

## 2. Files and Code Paths Inspected

| File Path | Component Inspected | Audit Focus |
| :--- | :--- | :--- |
| [`src/pipeline.py`](../src/pipeline.py) | `fetch_fuelhh_stream`, `fetch_windfor_stream` | Request parameter contracts, stream handling, timeout & headers. |
| [`src/pipeline.py`](../src/pipeline.py) | `normalize_fuelhh`, `normalize_windfor` | Strict UTC timestamp parsing, ISO 8601 formatting, numeric casting. |
| [`src/pipeline.py`](../src/pipeline.py) | `aggregate_fuelhh_to_hourly` | Settlement period pairing, floor division, period count integrity, NaN handling for missing periods. |
| [`src/pipeline.py`](../src/pipeline.py) | `select_deterministic_vintages` | Point-in-time filtering, group sorting, tie-breaking, dynamic fallback when runs are omitted. |
| [`src/pipeline.py`](../src/pipeline.py) | `build_analytical_dataset` | Column alignment, error math, percentage error with zero-division protection. |
| [`scripts/fetch_data.py`](../scripts/fetch_data.py) | CLI Argument Parser & Orchestration | Date boundary arithmetic ($D_{del} = D_{dec} + 1$), query safety buffers, output artifact generation. |
| [`data/processed/wind_analytical_dataset.parquet`](../data/processed/wind_analytical_dataset.parquet) | Binary Analytical Dataset | Schema types, row counts, null checks, min/max MW bounds. |
| [`data/processed/wind_analytical_dataset.csv`](../data/processed/wind_analytical_dataset.csv) | Text Analytical Dataset | Column names, formatting, exact string match with Parquet. |
| [`data/processed/data_quality_summary.json`](../data/processed/data_quality_summary.json) | Audit Metadata | Validation invariants, error metrics precision, record counts. |
| [`tests/test_pipeline.py`](../tests/test_pipeline.py) | Automated Pytest Suite | Invariant verification, regression test coverage. |

---

## 3. Independently Verified Metric Values

All metrics were recomputed from raw columns (`forecast_generation_mw` and `actual_generation_mean_mw`) in the generated Parquet dataset and cross-checked against `data_quality_summary.json`:

| Metric Name | Mathematical Formula | Independently Computed Value | Value in JSON / MD Summary | Discrepancy | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Observation Count ($N$)** | Count of hourly intervals | **744** | 744 | 0 | **EXACT MATCH** |
| **Constituent Actuals** | Half-hourly settlement periods | **1,488** | 1,488 | 0 | **EXACT MATCH** |
| **Mean Actual Generation** | $\frac{1}{N}\sum y_t$ | **11,283.557796 MW** | 11,283.56 MW | < 0.003 MW (rounding) | **MATCH** |
| **Mean Absolute Error (MAE)** | $\frac{1}{N}\sum \|e_t\|$ | **2,038.912634 MW** | 2,038.91 MW | < 0.003 MW (rounding) | **MATCH** |
| **Root Mean Squared Error (RMSE)** | $\sqrt{\frac{1}{N}\sum e_t^2}$ | **2,504.758653 MW** | 2,504.76 MW | < 0.002 MW (rounding) | **MATCH** |
| **Mean Bias Error (MBE)** | $\frac{1}{N}\sum e_t$ | **+1,747.887097 MW** | +1,747.89 MW | < 0.003 MW (rounding) | **MATCH** |
| **Normalized MAE (NMAE)** | $(\text{MAE} / \bar{y}) \times 100\%$ | **18.069767%** | 18.07% | < 0.001% (rounding) | **MATCH** |
| **Peak Overforecast Error** | $\max(e_t)$ | **+6,870.000000 MW** | +6,870.0 MW | 0.0 MW | **MATCH** |
| **Peak Underforecast Error** | $\min(e_t)$ | **-3,550.000000 MW** | -3,550.0 MW | 0.0 MW | **MATCH** |

### Verified Error Convention
- Formula: $e_t = \hat{y}_t - y_t$.
- Deviation across all 744 records: **0.000000 MW**.
- When $\hat{y}_t > y_t$: $e_t > 0$ (Overforecast, observed in 623 out of 744 hours, 83.7% of the time).
- When $\hat{y}_t < y_t$: $e_t < 0$ (Underforecast, observed in 121 out of 744 hours, 16.3% of the time).

---

## 4. Discrepancies Between Code, Artifacts, and Earlier Reports

During the independent audit, the following discrepancies were identified and cataloged:

### Discrepancy 1: Peak Overforecast / Underforecast in Chat Text vs. Stored Files
- **Context:** In the initial feasibility exploratory turn, an unconstrained single-slice test reported peak overforecast as `+8,228 MW` and peak underforecast as `-5,404 MW`.
- **Finding:** The actual generated production files (`wind_analytical_dataset.parquet`, `data_quality_summary.json`, and `docs/data_quality_report.md`) contain the verified values:
  - **Peak Overforecast:** `+6,870.0 MW` (Occurred on `2026-01-29T14:00:00Z`: Forecast 15,316 MW vs Actual 8,446 MW).
  - **Peak Underforecast:** `-3,550.0 MW` (Occurred on `2026-01-26T07:00:00Z`: Forecast 10,879 MW vs Actual 14,429 MW).
- **Resolution:** The stored artifacts are 100% correct and internally consistent.

### Discrepancy 2: Missing Half-Hour Aggregation Behavior (Remediated)
- **Context:** In `src/pipeline.py` lines 286-287, `actual_generation_sp1_mw` was defined as `first` and `actual_generation_sp2_mw` as `last`.
- **Finding:** If an hour contained only 1 settlement period, `first` and `last` would both extract the same period, masking the missing second half-hour.
- **Resolution:** The function was updated to explicitly compute $SP_1$ on odd periods and $SP_2$ on even periods with `np.nan` fallback, and add an explicit `is_complete_hour` boolean.

---

## 5. Delivery Window & Extraction Boundary Verification

### Record Accounting Audit

| Dimension | Raw Ingested Count | Window Filtered Count | Final Evaluation Count | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **FUELHH Records** | 1,584 | 1,488 | 1,488 | Raw covers 33 dates (`2026-01-01` to `2026-02-02`). Filtered to 31 delivery dates (`2026-01-02` to `2026-02-01`). |
| **Hourly Actual Intervals** | 792 | 744 | 744 | $1,488 / 2 = 744$ hourly observations. |
| **WINDFOR Publications** | 19,272 | 18,104 | 744 | Raw spans publications from `2025-12-30` to `2026-01-31`. 18,104 vintages target the delivery window. Exactly 1 vintage per hour is selected at cutoff. |

### Query Boundary Rationale
1. **FUELHH (`2026-01-01` to `2026-02-02`):**
   - The delivery window requires `2026-01-02` through `2026-02-01`.
   - Querying through `2026-02-02` guarantees that $SP_{48}$ on `2026-02-01` (spanning `23:30Z` to `24:00Z`) is never truncated by timezone or date-parsing boundary conditions.
2. **WINDFOR (`2025-12-30T00:00:00Z` to `2026-01-31T23:59:59Z`):**
   - For decision date `2026-01-01`, delivery is `2026-01-02`. Initial forecasts for `2026-01-02` were published as early as `2025-12-30 02:30Z` ($D-2$).
   - For decision date `2026-01-31`, delivery is `2026-02-01`. The forecast run used at 09:20 UTC was published on `2026-01-31 07:30Z`.
   - Every required forecast vintage is proven present.

---

## 6. Audit of the 09:20 UTC Decision Cutoff

### Exact Code & Configuration Setting
- **Core Library Default:** `src/pipeline.py` (Line 298): `cutoff_time: dt_time = dt_time(9, 20, 0)`.
- **CLI Default:** `scripts/fetch_data.py` (Line 48): `--cutoff-time 09:20:00`.
- **Source Label:** `EPEX SPOT GB Day-Ahead 60-Minute Auction Gate Closure (09:20 GMT/BST)`.

### Evidentiary Classification
- **Official Market Gate Closure [VERIFIED]:** Authoritative documentation from EPEX SPOT establishes that the order book for the Great Britain 60-Minute Day-Ahead Auction closes at **09:20 GMT/BST on D-1**.
- **Applicability to Utility Procurement [ASSUMPTION]:** The assignment scenario does not specify whether this specific utility clears volume via EPEX SPOT 60-minute, Nord Pool (09:50 GMT), EPEX 30-minute (15:30 GMT), or an internal portfolio benchmark (e.g. 11:00 UTC).
- **Audit Conclusion:** Labeling 09:20 as the market deadline is an **analytically sound assumption**, not an absolute contractual constraint. The pipeline correctly preserves parameter flexibility via `--cutoff-time` and `--cutoff-source`.

---

## 7. Automated Test Suite Execution Results

Executed the full regression suite (`pytest -v tests/test_pipeline.py`) containing 14 tests:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.1.1, pluggy-1.6.0
rootdir: windsignal
collected 14 items

tests/test_pipeline.py::test_timestamp_utc_normalization PASSED          [  7%]
tests/test_pipeline.py::test_date_boundaries_and_coverage PASSED         [ 14%]
tests/test_pipeline.py::test_no_look_ahead_bias_invariant PASSED         [ 21%]
tests/test_pipeline.py::test_deterministic_vintage_selection_logic PASSED [ 28%]
tests/test_pipeline.py::test_hourly_vs_half_hourly_aggregation PASSED    [ 35%]
tests/test_pipeline.py::test_production_hourly_period_count_integrity PASSED [ 42%]
tests/test_pipeline.py::test_duplicates_in_analytical_dataset PASSED     [ 50%]
tests/test_pipeline.py::test_no_missing_intervals_in_delivery_window PASSED [ 57%]
tests/test_pipeline.py::test_generation_values_sanity PASSED             [ 64%]
tests/test_pipeline.py::test_configurable_decision_cutoff_behavior PASSED [ 71%]
tests/test_pipeline.py::test_forecast_error_sign_convention PASSED       [ 78%]
tests/test_pipeline.py::test_single_period_missing_sp2_handling PASSED   [ 85%]
tests/test_pipeline.py::test_vintage_selection_fallback_when_0730_missing PASSED [ 92%]
tests/test_pipeline.py::test_vintage_selection_deterministic_tie_breaking PASSED [100%]

============================= 14 passed in 1.04s ==============================
```

---

## 8. Remaining Risks and Recommendations for Phase 2

1. **Systematic Overforecasting Bias Risk (Business Insight):**
   - In January 2026, the NGESO day-ahead forecast overforecasted wind generation with a Mean Bias Error of **+1,747.89 MW** (overforecast 83.7% of hours).
   - *Phase 2 Recommendation:* The analytics dashboard should prominently visualize this structural bias and quantify the volume/imbalance cost exposure for procurement managers.
2. **Daylight Saving Transition Handling (Future Horizon):**
   - During BST (UTC+1), the EPEX 09:20 local deadline becomes 08:20 UTC. The pipeline accepts UTC cutoffs directly, but a frontend time zone selector should display both UK Local time and UTC.
3. **Data Freshness / Automation:**
   - Ingested files are versioned in `data/processed/` and `data/raw/`. For public demo deployment, the backend should serve directly from these precomputed extracts to maintain sub-15ms response latency without calling external APIs.

---

## 9. Final Sign-Off

The data pipeline, interval aggregation engine, vintage selector, and benchmark calculations have passed all audit checks with zero defects remaining. The analytical foundation is **approved for Phase 2 product and API development**.
