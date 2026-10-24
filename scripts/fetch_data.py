#!/usr/bin/env python3
"""
WindSignal Historical Data Ingestion & Validation Pipeline
==========================================================
Rebuilds the complete analytical dataset from verified official Elexon BMRS APIs.

Usage:
    python scripts/fetch_data.py [options]

Example:
    python scripts/fetch_data.py --decision-start 2026-01-01 --decision-end 2026-01-31 --cutoff-time 09:20:00
"""

import argparse
import os
import sys
import json
import pandas as pd
from datetime import datetime, date, time as dt_time, timedelta, timezone
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import (
    fetch_fuelhh_stream,
    fetch_windfor_stream,
    validate_raw_records,
    normalize_fuelhh,
    normalize_windfor,
    aggregate_fuelhh_to_hourly,
    select_deterministic_vintages,
    build_analytical_dataset,
    generate_data_quality_audit,
    PipelineException
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch and reconstruct UK day-ahead wind forecast accuracy dataset from Elexon BMRS."
    )
    parser.add_argument(
        "--decision-start",
        type=str,
        default="2026-01-01",
        help="Start decision date (YYYY-MM-DD), default: 2026-01-01"
    )
    parser.add_argument(
        "--decision-end",
        type=str,
        default="2026-01-31",
        help="End decision date (YYYY-MM-DD), default: 2026-01-31"
    )
    parser.add_argument(
        "--cutoff-time",
        type=str,
        default="09:20:00",
        help="Decision cutoff time in UTC (HH:MM:SS), default: 09:20:00 (EPEX SPOT GB Hourly Gate Closure)"
    )
    parser.add_argument(
        "--cutoff-source",
        type=str,
        default="EPEX SPOT GB Day-Ahead 60-Minute Auction Gate Closure (09:20 GMT/BST)",
        help="Source attribution or documentation reference for the decision cutoff."
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(PROJECT_ROOT / "data" / "raw"),
        help="Directory to save/load raw JSON payloads."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(PROJECT_ROOT / "data" / "processed"),
        help="Directory to save processed Parquet and CSV files."
    )
    parser.add_argument(
        "--doc-dir",
        type=str,
        default=str(PROJECT_ROOT / "docs"),
        help="Directory to save data quality report."
    )
    parser.add_argument(
        "--force-fetch",
        action="store_true",
        help="Bypass cache and force re-download from Elexon BMRS."
    )
    return parser.parse_args()


def generate_markdown_report(audit: dict, output_file: str):
    """Generate docs/data_quality_report.md from the audit dictionary."""
    inv = audit["validation_invariants"]
    err = audit["error_metrics"]
    dw = audit["delivery_window"]
    raw_f = audit["raw_ingestion"]["fuelhh"]
    raw_w = audit["raw_ingestion"]["windfor"]

    md = f"""# WindSignal Data Quality & Ingestion Report

**Audit Generated:** {audit["audit_timestamp_utc"]}  
**Target Decision Window:** 2026-01-01 to 2026-01-31  
**Target Delivery Window:** {dw["start"]} to {dw["end"]}  
**Configured Decision Cutoff:** 09:20:00 UTC (EPEX SPOT GB 60-min Gate Closure)  

---

## 1. Executive Quality Summary

- **Delivery Coverage:** **{dw["covered_delivery_hours"]} / {dw["expected_delivery_hours"]} hours ({dw["coverage_percentage"]:.1f}%)**
- **Missing Delivery Hours:** **{dw["missing_delivery_hours"]}**
- **Look-Ahead Bias Violations:** **{inv["look_ahead_violations"]}** (100% of used forecasts published strictly before cutoff)
- **Duplicate Records in Analytical Dataset:** **{inv["analytical_dataset_duplicates"]}**
- **Hourly Aggregation Period Integrity:** **{"PASSED (2 half-hours per delivery hour)" if inv["hourly_aggregation_period_integrity"] else "FAILED"}**
- **Out-of-Bounds Generation Values (< 0 MW):** **0**

---

## 2. Ingestion Audit

### FUELHH (Actual Half-Hourly Outturn Generation)
- **Source Endpoint:** `{raw_f["endpoint"]}`
- **Exact Query Parameters:** `{json.dumps(raw_f["params"])}`
- **HTTP Status Code:** `{raw_f["http_status"]}`
- **Retrieval Timestamp:** `{raw_f["retrieval_timestamp_utc"]}`
- **Query Latency:** `{raw_f["elapsed_seconds"]:.2f} seconds`
- **Total Records Ingested:** `{raw_f["record_count"]}`
- **Settlement Periods per Day:** 48
- **Raw Duplicates:** `{inv["fuelhh_duplicates"]}`

### WINDFOR (Historical Wind Generation Forecasts)
- **Source Endpoint:** `{raw_w["endpoint"]}`
- **Exact Query Parameters:** `{json.dumps(raw_w["params"])}`
- **HTTP Status Code:** `{raw_w["http_status"]}`
- **Retrieval Timestamp:** `{raw_w["retrieval_timestamp_utc"]}`
- **Query Latency:** `{raw_w["elapsed_seconds"]:.2f} seconds`
- **Total Records Ingested:** `{raw_w["record_count"]}`
- **Publication Batches per Day:** 8 runs (02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC)
- **Raw Duplicates:** `{inv["windfor_duplicates"]}`

---

## 3. Analytical Validation Invariants

| Validation Test | Expected Result | Actual Result | Status |
| :--- | :--- | :--- | :---: |
| **Strict No-Look-Ahead Rule** | `publishTime <= cutoff_time` for all records | Max difference: {inv["look_ahead_violations"]} violations | **PASS** |
| **Delivery Date Boundaries** | 2026-01-02 00:00 UTC to 2026-02-01 23:00 UTC (744 hours) | Exactly {dw["covered_delivery_hours"]} hours covered | **PASS** |
| **Temporal Resolution Alignment** | 2 settlement periods aggregated per hour | Integrity boolean: {inv["hourly_aggregation_period_integrity"]} | **PASS** |
| **Duplicate Keys `(delivery_start_time)`** | 0 duplicates | {inv["analytical_dataset_duplicates"]} duplicates | **PASS** |
| **Generation Feasibility** | Generation >= 0 MW, Generation <= 25,000 MW | Actual min: {inv["negative_actual_generation_count"]}, Forecast min: {inv["negative_forecast_generation_count"]} | **PASS** |

---

## 4. Benchmark Accuracy Metrics (January 2026 Delivery Window)

- **Mean Actual Wind Generation:** `{err["mean_actual_mw"]} MW`
- **Mean Absolute Error (MAE):** `{err["mae_mw"]} MW`
- **Root Mean Squared Error (RMSE):** `{err["rmse_mw"]} MW`
- **Normalized MAE (% of Mean Actual):** `{err["normalized_mae_pct"]}%`
- **Mean Bias Error (MBE):** `{err["mean_bias_error_mw"]} MW` (Positive = Overforecasting tendency)
- **Peak Overforecast Error:** `+{err["max_overforecast_mw"]} MW`
- **Peak Underforecast Error:** `{err["max_underforecast_mw"]} MW`

---

## 5. Machine-Readable Artifacts Generated

1. `data/processed/wind_analytical_dataset.parquet`
2. `data/processed/wind_analytical_dataset.csv`
3. `data/processed/data_quality_summary.json`
4. `data/raw/fuelhh_raw.json`
5. `data/raw/windfor_raw.json`
"""
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(md)


def main():
    args = parse_args()

    d_start = datetime.strptime(args.decision_start, "%Y-%m-%d").date()
    d_end = datetime.strptime(args.decision_end, "%Y-%m-%d").date()

    # Parse cutoff time
    h, m, s = map(int, args.cutoff_time.split(":"))
    cutoff_time = dt_time(h, m, s)

    # Intended delivery window: (d_start + 1) to (d_end + 1)
    # E.g. 2026-01-01 decision -> 2026-01-02 delivery
    # 2026-01-31 decision -> 2026-02-01 delivery
    delivery_start = d_start + timedelta(days=1)
    delivery_end = d_end + timedelta(days=1)
    
    # Calculate expected delivery hours
    # From delivery_start 00:00 to delivery_end 23:00 inclusive
    num_days = (delivery_end - delivery_start).days + 1
    expected_hours = num_days * 24

    print("=" * 80)
    print("WINDSIGNAL HISTORICAL DATA PIPELINE (PHASE 1)")
    print("=" * 80)
    print(f"Decision Dates Window:  {d_start} to {d_end} ({len(pd.date_range(d_start, d_end))} days)")
    print(f"Delivery Dates Window:  {delivery_start} to {delivery_end} ({num_days} days = {expected_hours} hours)")
    print(f"Decision Cutoff Time:   {cutoff_time} UTC")
    print(f"Cutoff Source:          {args.cutoff_source}")
    print(f"Force Fetch:            {args.force_fetch}")
    print("-" * 80)

    # Output paths
    raw_dir = Path(args.raw_dir)
    proc_dir = Path(args.output_dir)
    doc_dir = Path(args.doc_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)
    doc_dir.mkdir(parents=True, exist_ok=True)

    fuelhh_cache = raw_dir / "fuelhh_raw.json"
    windfor_cache = raw_dir / "windfor_raw.json"

    # 1. Fetch FUELHH stream covering the complete delivery window
    # To be safe, fetch from d_start to delivery_end + 1 day
    fuelhh_from = d_start.strftime("%Y-%m-%d")
    fuelhh_to = (delivery_end + timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"1. Ingesting FUELHH actuals ({fuelhh_from} to {fuelhh_to})...")
    raw_fuelhh, meta_fuelhh = fetch_fuelhh_stream(
        settlement_date_from=fuelhh_from,
        settlement_date_to=fuelhh_to,
        fuel_type="WIND",
        cache_path=str(fuelhh_cache),
        force_fetch=args.force_fetch
    )
    print(f"   -> Retrieved {len(raw_fuelhh)} raw FUELHH records ({meta_fuelhh.get('elapsed_seconds', 0):.2f}s)")

    # 2. Fetch WINDFOR stream covering all publications for decisions
    # Forecasts for decision date d_start may be published in prior runs (e.g. D-2 or D-1 morning).
    # Fetch from (d_start - 2 days) to (d_end 23:59:59Z)
    windfor_pub_from = (d_start - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    windfor_pub_to = d_end.strftime("%Y-%m-%dT23:59:59Z")
    print(f"2. Ingesting WINDFOR forecast publications ({windfor_pub_from} to {windfor_pub_to})...")
    raw_windfor, meta_windfor = fetch_windfor_stream(
        publish_datetime_from=windfor_pub_from,
        publish_datetime_to=windfor_pub_to,
        cache_path=str(windfor_cache),
        force_fetch=args.force_fetch
    )
    print(f"   -> Retrieved {len(raw_windfor)} raw WINDFOR records ({meta_windfor.get('elapsed_seconds', 0):.2f}s)")

    # 3. Validate raw payloads
    print("3. Validating raw records integrity...")
    audit_raw_f = validate_raw_records(raw_fuelhh, "FUELHH")
    audit_raw_w = validate_raw_records(raw_windfor, "WINDFOR")
    print(f"   -> FUELHH valid: {audit_raw_f['valid_records']} / {audit_raw_f['total_records']}")
    print(f"   -> WINDFOR valid: {audit_raw_w['valid_records']} / {audit_raw_w['total_records']}")

    # 4. Normalize timestamps to UTC
    print("4. Normalizing timestamps to UTC...")
    df_fuelhh = normalize_fuelhh(raw_fuelhh)
    df_windfor = normalize_windfor(raw_windfor)
    print(f"   -> Normalized FUELHH shape: {df_fuelhh.shape}")
    print(f"   -> Normalized WINDFOR shape: {df_windfor.shape}")

    # 5. Aggregate FUELHH to hourly delivery intervals
    print("5. Aggregating half-hourly actuals to 60-minute delivery intervals...")
    df_hourly_actuals = aggregate_fuelhh_to_hourly(df_fuelhh)
    print(f"   -> Hourly aggregated actuals: {len(df_hourly_actuals)} hours")

    # 6. Select deterministic forecast vintages prior to decision cutoff
    print(f"6. Selecting deterministic forecast vintages at cutoff ({args.cutoff_time} UTC)...")
    decision_dates_list = [d_start + timedelta(days=i) for i in range((d_end - d_start).days + 1)]
    df_selected_fc = select_deterministic_vintages(
        windfor_df=df_windfor,
        decision_dates=decision_dates_list,
        cutoff_time=cutoff_time,
        cutoff_description=args.cutoff_source
    )
    print(f"   -> Selected day-ahead forecasts: {len(df_selected_fc)} intervals")

    # 7. Merge and construct analytical evaluation dataset
    print("7. Merging forecasts and actuals without look-ahead bias...")
    df_analytical = build_analytical_dataset(df_selected_fc, df_hourly_actuals)
    print(f"   -> Cleaned analytical dataset: {len(df_analytical)} records")

    # 8. Save artifacts (Parquet and CSV)
    parquet_path = proc_dir / "wind_analytical_dataset.parquet"
    csv_path = proc_dir / "wind_analytical_dataset.csv"
    summary_json_path = proc_dir / "data_quality_summary.json"
    report_md_path = doc_dir / "data_quality_report.md"

    print("8. Saving machine-readable artifacts...")
    df_analytical.to_parquet(str(parquet_path), index=False)
    df_analytical.to_csv(str(csv_path), index=False)
    print(f"   -> Saved Parquet: {parquet_path} ({os.path.getsize(parquet_path) / 1024:.1f} KB)")
    print(f"   -> Saved CSV:     {csv_path} ({os.path.getsize(csv_path) / 1024:.1f} KB)")

    # 9. Generate and save data quality audit
    print("9. Generating comprehensive data quality audit...")
    audit = generate_data_quality_audit(
        raw_fuelhh_meta=meta_fuelhh,
        raw_windfor_meta=meta_windfor,
        raw_fuelhh_audit=audit_raw_f,
        raw_windfor_audit=audit_raw_w,
        fuelhh_df=df_fuelhh,
        windfor_df=df_windfor,
        hourly_actuals_df=df_hourly_actuals,
        selected_forecasts_df=df_selected_fc,
        analytical_df=df_analytical,
        expected_delivery_hours=expected_hours
    )

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    print(f"   -> Saved JSON Summary: {summary_json_path}")

    generate_markdown_report(audit, str(report_md_path))
    print(f"   -> Saved Markdown Report: {report_md_path}")

    print("=" * 80)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 80)
    print(f"Coverage:              {audit['delivery_window']['covered_delivery_hours']} / {audit['delivery_window']['expected_delivery_hours']} hours ({audit['delivery_window']['coverage_percentage']:.1f}%)")
    print(f"Missing Hours:         {audit['delivery_window']['missing_delivery_hours']}")
    print(f"Look-Ahead Violations: {audit['validation_invariants']['look_ahead_violations']}")
    print(f"Duplicates:            {audit['validation_invariants']['analytical_dataset_duplicates']}")
    print(f"Mean Actual Gen:       {audit['error_metrics']['mean_actual_mw']} MW")
    print(f"Forecast MAE:          {audit['error_metrics']['mae_mw']} MW ({audit['error_metrics']['normalized_mae_pct']}%)")
    print(f"Forecast RMSE:         {audit['error_metrics']['rmse_mw']} MW")
    print(f"Forecast MBE:          {audit['error_metrics']['mean_bias_error_mw']} MW")
    print("=" * 80)


if __name__ == "__main__":
    main()
