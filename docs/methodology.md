# WindSignal Analytical Methodology: Interval Alignment & Vintage Selection

**Project:** WindSignal — UK Day-Ahead Wind Generation Forecast Accuracy Application  
**Target Window:** January 2026 Purchase Decisions (Delivery: 2026-01-02 to 2026-02-01 inclusive)  
**Author:** Antigravity Autonomous Systems Engineering Team  
**Date:** 2026-10-24  

---

## 1. Overview and Core Objectives

The primary analytical objective of the **WindSignal** platform is to assess the operational accuracy of the National Grid Electricity System Operator (NGESO / NESO) wind generation forecasts (`WINDFOR`) against actual transmission-system generation outturn (`FUELHH`) for electricity procurement decisions made across January 2026.

To provide genuine decision support to a utility trading desk, the evaluation must satisfy two non-negotiable principles:
1. **Strict Elimination of Look-Ahead Bias:** At any decision point $C$, an analytical system must only utilize information that was published and accessible to market participants prior to or at time $C$.
2. **Mathematically Rigorous Interval Alignment:** Actual outturn recorded at 30-minute settlement periods must be mapped onto 60-minute forecast intervals without temporal leakage or artificial distortion.

---

## 2. Dataset Semantics and Characteristics

Both datasets are ingested directly from official Elexon Insights Solution stream endpoints:

### A. FUELHH (Actual Generation by Fuel Type)
- **Endpoint:** `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
- **Cadence:** Half-hourly (30-minute settlement periods).
- **Scope:** Great Britain transmission-system outturn by fuel type, aggregated from operational metering of Balancing Mechanism (BM) Units.
- **Population:** Transmission-connected wind farms and large embedded BM wind farms visible to the System Operator. Unmetered, small distributed micro-generation is excluded.
- **Timestamp Fields:**
  - `startTime`: Beginning of the 30-minute delivery interval in UTC (e.g. `2026-01-02T12:00:00Z` for SP 25).
  - `publishTime`: Timestamp when the outturn record was calculated and made available (typically 30–60 minutes post-delivery).
  - `settlementDate`: Calendar date of the settlement day (`YYYY-MM-DD`).
  - `settlementPeriod`: Integer from 1 to 48 (or 46/50 on clock-change days).
  - `generation`: Average power output across the 30-minute window in integer Megawatts (MW).

### B. WINDFOR (Wind Generation Forecast)
- **Endpoint:** `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
- **Cadence:** Hourly (60-minute forecast intervals).
- **Update Frequency:** Published up to 8 times daily by NGESO at scheduled times:  
  `02:30`, `04:30`, `07:30`, `09:30`, `11:30`, `15:30`, `18:30`, and `22:30 UTC`.
- **Forecast Horizon:** Rolling forward projection spanning ~72 to 84 hours (typically 73 discrete hourly intervals per publication batch).
- **Population:** Wind farms visible to the ESO with operational metering.
- **Timestamp Fields:**
  - `startTime`: Target delivery hour in UTC (always at `:00:00Z`, corresponding to odd settlement periods 1, 3, 5, ..., 47).
  - `publishTime`: Timestamp when this specific forecast vintage was produced and issued by NGESO.
  - `generation`: Projected average wind power output across the target hour in integer Megawatts (MW).

---

## 3. Temporal Resolution Alignment

### The Problem: 60-Minute Forecast vs. 30-Minute Actuals
A fundamental property of Elexon BMRS data is the resolution divergence between `WINDFOR` (hourly) and `FUELHH` (half-hourly).

Each electricity delivery day in Great Britain comprises 48 half-hourly Settlement Periods ($SP_1$ to $SP_{48}$), whereas WINDFOR provides 24 hourly forecast steps.

### Alignment Formulation
In accordance with BSC settlement rules and standard energy procurement conventions, an hourly delivery period beginning at hour $H$ (where $H \in \{00, 01, \dots, 23\}$) covers two consecutive half-hourly settlement periods:
- **First Half-Hour ($SP_{odd}$):** $H:00$ to $H:30$ (Settlement Period $2H + 1$)
- **Second Half-Hour ($SP_{even}$):** $H:30$ to $(H+1):00$ (Settlement Period $2H + 2$)

To compute the actual wind power generated during that hour on a basis directly comparable to the hourly forecast, the analytical engine computes the **arithmetic mean** of the two settlement periods:

$$\text{ActualMW}_H = \frac{\text{OutturnMW}(SP_{2H+1}) + \text{OutturnMW}(SP_{2H+2})}{2}$$

#### Settlement Period Mapping Table:
| Delivery Hour (UTC) | Start Time UTC | Settlement Periods | Actual MW Formula |
| :---: | :---: | :---: | :---: |
| 00:00 – 01:00 | `YYYY-MM-DDTHH:00:00Z` | SP 1, SP 2 | $\frac{SP_1 + SP_2}{2}$ |
| 01:00 – 02:00 | `YYYY-MM-DDTHH:01:00Z` | SP 3, SP 4 | $\frac{SP_3 + SP_4}{2}$ |
| ... | ... | ... | ... |
| 12:00 – 13:00 | `YYYY-MM-DDTHH:12:00Z` | SP 25, SP 26 | $\frac{SP_{25} + SP_{26}}{2}$ |
| ... | ... | ... | ... |
| 23:00 – 24:00 | `YYYY-MM-DDTHH:23:00Z` | SP 47, SP 48 | $\frac{SP_{47} + SP_{48}}{2}$ |

**Validation Invariant:** Every delivery hour must have `period_count == 2`. If an hour contains fewer than 2 settlement periods, it is flagged as an incomplete delivery interval.

---

## 4. Market Deadlines & Configurable Decision Cutoffs

### Great Britain Wholesale Day-Ahead Market Structure
In the UK electricity market, wholesale day-ahead procurement decisions are executed via power exchange auctions that establish clearing prices and physical schedules for delivery day $D$.

Trading desks must finalize order submissions prior to the auction order book deadline ("Gate Closure"):

1. **EPEX SPOT GB Day-Ahead 60-Minute Auction (Primary Market Benchmark):**
   - **Gate Closure:** **09:20 GMT/BST on day D-1**.
   - **Results Published:** 09:30 GMT/BST.
   - **Relevance:** This is the primary and most liquid auction used by UK energy suppliers to hedge hourly wind shapes.
2. **Nord Pool GB Day-Ahead Auction (formerly N2EX):**
   - **Gate Closure:** **09:50 GMT/BST on day D-1** (10:50 CET).
   - **Results Published:** 10:00 GMT/BST.
3. **EPEX SPOT GB Day-Ahead 30-Minute Auction:**
   - **Gate Closure:** **15:30 GMT/BST on day D-1**.
   - **Results Published:** 15:45 GMT/BST.

### Interplay with NGESO Forecast Publication Schedule
Because NGESO publishes `WINDFOR` at fixed times (`02:30`, `04:30`, `07:30`, `09:30`, `11:30`, `15:30`, `18:30`, `22:30 UTC`), the forecast vintage available to a procurement desk depends directly on the chosen gate closure:

- **For EPEX SPOT 09:20 Cutoff:** The **07:30 UTC** run is the latest publication issued prior to 09:20. The 09:30 run is published *after* the auction closes and cannot be used without introducing look-ahead bias.
- **For Nord Pool 09:50 Cutoff:** While the 09:30 run is published 20 minutes before gate closure, trading desks require data processing and order book preparation time; nonetheless, the pipeline deterministically selects whichever run was timestamped $\le \text{cutoff}$.
- **For Afternoon 15:30 Cutoff:** The **11:30 UTC** run is the latest publication available prior to 15:30.

### Timezone and Daylight Saving Considerations
- **January Decisions:** Great Britain observes Greenwich Mean Time (GMT = UTC+0). All local auction deadlines map 1:1 to UTC.
- **British Summer Time (BST = UTC+1):** During summer months, 09:20 BST corresponds to **08:20 UTC**. The latest pre-cutoff forecast remains the 07:30 UTC run.
- **Architecture Principle:** The pipeline accepts an explicit `--cutoff-time` parameter (default `09:20:00` UTC) and records the parameter alongside human-readable attribution (`--cutoff-source`) in all output metadata.

---

## 5. Point-in-Time Vintage Selection Algorithm

To guarantee zero look-ahead bias, forecast selection is implemented as a deterministic point-in-time filter:

Let:
- $D_{dec}$ be the decision date.
- $D_{del} = D_{dec} + 1\text{ day}$ be the target delivery date.
- $T_{cutoff} = \text{combine}(D_{dec}, \text{cutoff\_time})$ be the decision cutoff timestamp in UTC.
- $H \in \{00, 01, \dots, 23\}$ be the target delivery hour.
- $T_{del} = \text{combine}(D_{del}, H:00:00\text{ UTC})$ be the delivery start timestamp.
- $\mathcal{V}(T_{del})$ be the set of all historical WINDFOR publications targeting delivery time $T_{del}$.

The selected forecast vintage $\hat{y}(T_{del})$ is defined as:

$$\hat{y}(T_{del}) = \text{Record}_{\text{WINDFOR}}(T_{del}, P^*)$$

where the optimal publication timestamp $P^*$ satisfies:

$$P^* = \max \left\{ P \;\middle|\; (T_{del}, P) \in \mathcal{V}(T_{del}) \;\land\; P \le T_{cutoff} \right\}$$

### Invariant Checks Enforced in Pipeline:
1. **$P^* \le T_{cutoff}$:** Strictly asserts that the publication time is at or before the decision deadline.
2. **$T_{del} > P^*$:** Strictly asserts that delivery is strictly in the future relative to the publication time (positive lead time).
3. **Determinism:** If multiple records share identical $(T_{del}, P)$, duplicates are deduplicated deterministically by index.

---

## 6. Error Metrics and Mathematical Formulations

For each delivery hour $t = 1, \dots, N$:
- $\hat{y}_t = \text{forecast\_generation\_mw}$ (Selected forecast at cutoff)
- $y_t = \text{actual\_generation\_mean\_mw}$ (Hourly aggregated actual outturn)

### 1. Forecast Error (Signed Error / Bias):
$$e_t = \hat{y}_t - y_t \quad (\text{MW})$$
- $e_t > 0$: **Overforecast** (Expected more wind than realized; utility must buy deficit on short-term market or balancing mechanism).
- $e_t < 0$: **Underforecast** (Realized more wind than expected; surplus spill or sell at discount).

### 2. Absolute Error:
$$|e_t| = |\hat{y}_t - y_t| \quad (\text{MW})$$

### 3. Mean Absolute Error (MAE):
$$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |e_t| \quad (\text{MW})$$

### 4. Root Mean Squared Error (RMSE):
$$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N e_t^2} \quad (\text{MW})$$

### 5. Mean Bias Error (MBE):
$$\text{MBE} = \frac{1}{N} \sum_{t=1}^N e_t \quad (\text{MW})$$

### 6. Normalized Mean Absolute Error (NMAE):
$$\text{NMAE} = \frac{\text{MAE}}{\bar{y}} \times 100\% \quad \text{where } \bar{y} = \frac{1}{N}\sum_{t=1}^N y_t$$

---

## 7. Quality Assurance Invariants

The automated test suite (`tests/test_pipeline.py`) validates the following core invariants across the entire ingested dataset:

1. **No-Look-Ahead Invariant:** $\forall t, P_t \le C_t$. Look-ahead violation count must equal zero.
2. **Boundary Coverage:** Exactly 744 hours covered from `2026-01-02 00:00:00Z` to `2026-02-01 23:00:00Z`.
3. **Settlement Period Pairing:** For all delivery hours, $SP_{start}$ is odd, and $SP_{end} = SP_{start} + 1$.
4. **Physical Sanity:** Generation values satisfy $0 \le \text{MW} < 35,000\text{ MW}$ (within GB physical grid boundaries).
5. **No Nulls or Duplicates:** Exactly 0 duplicate timestamps on `delivery_start_time_utc`.
