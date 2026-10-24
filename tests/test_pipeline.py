"""
Unit and Integration Tests for WindSignal Data Pipeline
======================================================
Tests timestamp normalization, date boundaries, vintage selection,
duplicate detection, missing intervals, and strict no-look-ahead invariants.
"""

import os
import sys
import json
from datetime import datetime, date, time as dt_time, timedelta, timezone
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import (
    normalize_fuelhh,
    normalize_windfor,
    aggregate_fuelhh_to_hourly,
    select_deterministic_vintages,
    build_analytical_dataset,
    validate_raw_records,
    generate_data_quality_audit
)
PROCESSED_PARQUET = PROJECT_ROOT / "data" / "processed" / "wind_analytical_dataset.parquet"
RAW_FUELHH_JSON = PROJECT_ROOT / "data" / "raw" / "fuelhh_raw.json"
RAW_WINDFOR_JSON = PROJECT_ROOT / "data" / "raw" / "windfor_raw.json"


@pytest.fixture(scope="session")
def loaded_analytical_dataset():
    """Loads the generated analytical dataset from Parquet."""
    assert PROCESSED_PARQUET.exists(), f"Processed dataset missing at {PROCESSED_PARQUET}"
    df = pd.read_parquet(PROCESSED_PARQUET)
    return df


@pytest.fixture(scope="session")
def raw_data_payloads():
    """Loads cached raw JSON payloads."""
    assert RAW_FUELHH_JSON.exists(), f"FUELHH cache missing at {RAW_FUELHH_JSON}"
    assert RAW_WINDFOR_JSON.exists(), f"WINDFOR cache missing at {RAW_WINDFOR_JSON}"
    with open(RAW_FUELHH_JSON, "r", encoding="utf-8") as f:
        fuelhh = json.load(f)["records"]
    with open(RAW_WINDFOR_JSON, "r", encoding="utf-8") as f:
        windfor = json.load(f)["records"]
    return fuelhh, windfor


# -------------------------------------------------------------------------
# 1. Timestamp Normalization & UTC Formatting Tests
# -------------------------------------------------------------------------

def test_timestamp_utc_normalization(raw_data_payloads):
    fuelhh_raw, windfor_raw = raw_data_payloads
    df_f = normalize_fuelhh(fuelhh_raw[:50])
    df_w = normalize_windfor(windfor_raw[:50])

    # Check timezone info is explicitly UTC
    assert str(df_f["start_time_utc"].dt.tz) in ["UTC", "datetime.timezone.utc"]
    assert str(df_f["publish_time_utc"].dt.tz) in ["UTC", "datetime.timezone.utc"]
    assert str(df_w["start_time_utc"].dt.tz) in ["UTC", "datetime.timezone.utc"]
    assert str(df_w["publish_time_utc"].dt.tz) in ["UTC", "datetime.timezone.utc"]

    # Check original strings preserved
    assert "raw_start_time" in df_f.columns
    assert "raw_publish_time" in df_f.columns
    assert "raw_start_time" in df_w.columns
    assert "raw_publish_time" in df_w.columns


# -------------------------------------------------------------------------
# 2. Date Boundaries and Delivery Coverage Tests
# -------------------------------------------------------------------------

def test_date_boundaries_and_coverage(loaded_analytical_dataset):
    df = loaded_analytical_dataset
    # Expected: 31 delivery days (2026-01-02 to 2026-02-01 inclusive)
    # 31 * 24 = 744 hours
    assert len(df) == 744, f"Expected exactly 744 hours, got {len(df)}"

    start_dt = pd.to_datetime(df["delivery_start_time_utc"].min())
    end_dt = pd.to_datetime(df["delivery_start_time_utc"].max())

    expected_start = pd.to_datetime("2026-01-02T00:00:00Z")
    expected_end = pd.to_datetime("2026-02-01T23:00:00Z")

    assert start_dt == expected_start, f"Start interval {start_dt} != {expected_start}"
    assert end_dt == expected_end, f"End interval {end_dt} != {expected_end}"

    # Verify decision date is exactly delivery date - 1 day
    for _, row in df.iterrows():
        dec_d = pd.to_datetime(row["decision_date"]).date()
        del_d = pd.to_datetime(row["delivery_date"]).date()
        assert del_d - dec_d == timedelta(days=1), f"Mismatch: dec={dec_d}, del={del_d}"


# -------------------------------------------------------------------------
# 3. Strict No-Look-Ahead Bias Invariant Tests
# -------------------------------------------------------------------------

def test_no_look_ahead_bias_invariant(loaded_analytical_dataset):
    df = loaded_analytical_dataset
    cutoff_series = pd.to_datetime(df["cutoff_time_utc"])
    pub_series = pd.to_datetime(df["forecast_publish_time_utc"])

    # Core requirement: publication timestamp must strictly precede or equal the cutoff timestamp
    violations = df[pub_series > cutoff_series]
    assert len(violations) == 0, f"Found {len(violations)} look-ahead violations: {violations}"

    # Check lead time is positive (forecast must be published before delivery starts)
    del_series = pd.to_datetime(df["delivery_start_time_utc"])
    assert (del_series > pub_series).all(), "Found forecasts published after delivery start!"


def test_deterministic_vintage_selection_logic():
    """Synthetic test ensuring vintage selector chooses the latest valid run."""
    synthetic_records = [
        # Target interval 2026-01-05 12:00:00 UTC
        # Run 1: D-2 (2026-01-03 11:30)
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-03T11:30:00Z", "generation": 1000},
        # Run 2: D-1 Morning (2026-01-04 07:30) - PRE CUTOFF (09:20)
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T07:30:00Z", "generation": 1500},
        # Run 3: D-1 Midday (2026-01-04 11:30) - POST CUTOFF (09:20)
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T11:30:00Z", "generation": 2000},
        # Run 4: Realtime (2026-01-05 11:30) - POST DELIVERY
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-05T11:30:00Z", "generation": 2500},
    ]
    df_syn = normalize_windfor(synthetic_records)
    selected = select_deterministic_vintages(
        windfor_df=df_syn,
        decision_dates=[date(2026, 1, 4)],
        cutoff_time=dt_time(9, 20, 0),
        cutoff_description="Test Cutoff 09:20"
    )

    assert len(selected) == 1
    chosen = selected.iloc[0]
    # Must select Run 2 (1500 MW published at 07:30), NOT Run 3 (11:30) or Run 4
    assert chosen["forecast_generation_mw"] == 1500
    assert chosen["forecast_publish_time_utc"] == pd.to_datetime("2026-01-04T07:30:00Z")


# -------------------------------------------------------------------------
# 4. Hourly vs Half-Hourly Aggregation Tests
# -------------------------------------------------------------------------

def test_hourly_vs_half_hourly_aggregation():
    # Synthetic half-hourly actuals for Hour 10:00 (SP 21 and 22)
    syn_fuelhh = [
        {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-02T10:30:00Z",
         "settlementDate": "2026-01-02", "settlementPeriod": 21, "fuelType": "WIND", "generation": 12000},
        {"startTime": "2026-01-02T10:30:00Z", "publishTime": "2026-01-02T11:00:00Z",
         "settlementDate": "2026-01-02", "settlementPeriod": 22, "fuelType": "WIND", "generation": 14000},
    ]
    df_norm = normalize_fuelhh(syn_fuelhh)
    hourly = aggregate_fuelhh_to_hourly(df_norm)

    assert len(hourly) == 1
    row = hourly.iloc[0]
    assert row["period_count"] == 2
    assert row["start_settlement_period"] == 21
    assert row["end_settlement_period"] == 22
    assert row["actual_generation_mean_mw"] == 13000.0  # (12000 + 14000) / 2
    assert row["actual_generation_min_mw"] == 12000.0
    assert row["actual_generation_max_mw"] == 14000.0


def test_production_hourly_period_count_integrity(loaded_analytical_dataset):
    df = loaded_analytical_dataset
    # Every row in analytical dataset represents 2 settlement periods
    assert (df["start_settlement_period"] % 2 != 0).all(), "Start SP must be odd"
    assert (df["end_settlement_period"] == df["start_settlement_period"] + 1).all()


# -------------------------------------------------------------------------
# 5. Duplicate and Missing Interval Detection Tests
# -------------------------------------------------------------------------

def test_duplicates_in_analytical_dataset(loaded_analytical_dataset):
    df = loaded_analytical_dataset
    duplicates = df[df.duplicated(subset=["delivery_start_time_utc"], keep=False)]
    assert len(duplicates) == 0, f"Found duplicate delivery start times: {duplicates}"


def test_no_missing_intervals_in_delivery_window(loaded_analytical_dataset):
    df = loaded_analytical_dataset
    dt_series = pd.to_datetime(df["delivery_start_time_utc"])
    expected_range = pd.date_range("2026-01-02 00:00:00Z", "2026-02-01 23:00:00Z", freq="1h")

    missing = set(expected_range) - set(dt_series)
    assert len(missing) == 0, f"Missing intervals detected: {sorted(missing)}"


# -------------------------------------------------------------------------
# 6. Generation Value Sanity Tests
# -------------------------------------------------------------------------

def test_generation_values_sanity(loaded_analytical_dataset):
    df = loaded_analytical_dataset
    # No negative generation
    assert (df["forecast_generation_mw"] >= 0).all(), "Found negative forecast generation"
    assert (df["actual_generation_mean_mw"] >= 0).all(), "Found negative actual generation"

    # UK wind generation plausible physical ceiling (< 35 GW)
    assert (df["forecast_generation_mw"] < 35000).all()
    assert (df["actual_generation_mean_mw"] < 35000).all()

    # Numeric check
    assert not df["forecast_generation_mw"].isna().any()
    assert not df["actual_generation_mean_mw"].isna().any()
    assert not df["forecast_error_mw"].isna().any()


# -------------------------------------------------------------------------
# 7. Configurable Decision Cutoff Behavioral Tests
# -------------------------------------------------------------------------

def test_configurable_decision_cutoff_behavior(raw_data_payloads):
    _, windfor_raw = raw_data_payloads
    df_w = normalize_windfor(windfor_raw)

    decision_day = [date(2026, 1, 10)]

    # 1. Early morning cutoff 06:00 UTC (before the 07:30 run)
    # Latest available run should be 04:30 UTC
    sel_0600 = select_deterministic_vintages(
        df_w, decision_day, cutoff_time=dt_time(6, 0, 0), cutoff_description="Early Cutoff"
    )
    # 2. EPEX 60-min cutoff 09:20 UTC (after 07:30, before 09:30)
    # Latest available run should be 07:30 UTC
    sel_0920 = select_deterministic_vintages(
        df_w, decision_day, cutoff_time=dt_time(9, 20, 0), cutoff_description="EPEX 09:20"
    )
    # 3. Afternoon cutoff 16:00 UTC (after 15:30 run)
    # Latest available run should be 15:30 UTC
    sel_1600 = select_deterministic_vintages(
        df_w, decision_day, cutoff_time=dt_time(16, 0, 0), cutoff_description="Afternoon 16:00"
    )

    pub_0600 = sel_0600["forecast_publish_time_utc"].dt.time.unique()
    pub_0920 = sel_0920["forecast_publish_time_utc"].dt.time.unique()
    pub_1600 = sel_1600["forecast_publish_time_utc"].dt.time.unique()

    assert dt_time(4, 30) in pub_0600, f"Expected 04:30 run for 06:00 cutoff, got {pub_0600}"
    assert dt_time(7, 30) in pub_0920, f"Expected 07:30 run for 09:20 cutoff, got {pub_0920}"
    assert dt_time(15, 30) in pub_1600, f"Expected 15:30 run for 16:00 cutoff, got {pub_1600}"


# -------------------------------------------------------------------------
# 8. Phase 1.1 Audit Regression Tests
# -------------------------------------------------------------------------

def test_forecast_error_sign_convention(loaded_analytical_dataset):
    """
    Check 2: Confirm error = forecast - actual.
    Positive error represents wind overforecast; negative error represents wind underforecast.
    """
    df = loaded_analytical_dataset
    # Verify exact mathematical definition across all 744 rows
    diff = df["forecast_error_mw"] - (df["forecast_generation_mw"] - df["actual_generation_mean_mw"])
    assert (diff.abs() < 1e-9).all(), "forecast_error_mw must strictly equal forecast - actual!"

    # Verify semantic behavior:
    # Overforecast: forecast > actual -> error > 0
    overforecasts = df[df["forecast_generation_mw"] > df["actual_generation_mean_mw"]]
    assert (overforecasts["forecast_error_mw"] > 0).all()

    # Underforecast: forecast < actual -> error < 0
    underforecasts = df[df["forecast_generation_mw"] < df["actual_generation_mean_mw"]]
    assert (underforecasts["forecast_error_mw"] < 0).all()


def test_single_period_missing_sp2_handling():
    """
    Check 3: Confirm missing settlement period does not duplicate sp1 value,
    returns NaN for missing sp2, and flags is_complete_hour as False.
    """
    syn_single = [
        {"startTime": "2026-01-02T10:00:00Z", "publishTime": "2026-01-02T10:30:00Z",
         "settlementDate": "2026-01-02", "settlementPeriod": 21, "fuelType": "WIND", "generation": 12000}
    ]
    df_norm = normalize_fuelhh(syn_single)
    hourly = aggregate_fuelhh_to_hourly(df_norm)

    assert len(hourly) == 1
    row = hourly.iloc[0]
    assert row["period_count"] == 1
    assert not bool(row["is_complete_hour"])
    assert row["actual_generation_sp1_mw"] == 12000.0
    assert pd.isna(row["actual_generation_sp2_mw"])  # Must be NaN, NOT 12000.0


def test_vintage_selection_fallback_when_0730_missing():
    """
    Check 4: Confirm that if 07:30 publication is omitted, the selector
    dynamically falls back to 04:30 rather than assuming 07:30.
    """
    synthetic_records = [
        # Target interval 2026-01-05 12:00:00 UTC
        # Run 1: 02:30 UTC
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T02:30:00Z", "generation": 1100},
        # Run 2: 04:30 UTC - LATEST PRE-CUTOFF RUN AVAILABLE (07:30 omitted!)
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T04:30:00Z", "generation": 1350},
        # Run 3: 09:30 UTC - POST-CUTOFF RUN
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T09:30:00Z", "generation": 1800},
    ]
    df_syn = normalize_windfor(synthetic_records)
    selected = select_deterministic_vintages(
        windfor_df=df_syn,
        decision_dates=[date(2026, 1, 4)],
        cutoff_time=dt_time(9, 20, 0),
        cutoff_description="EPEX 09:20 Cutoff"
    )

    assert len(selected) == 1
    chosen = selected.iloc[0]
    # Must dynamically select the 04:30 run (1350 MW), not crash or assume 07:30
    assert chosen["forecast_generation_mw"] == 1350
    assert chosen["forecast_publish_time_utc"] == pd.to_datetime("2026-01-04T04:30:00Z")


def test_vintage_selection_deterministic_tie_breaking():
    """
    Check 4: Confirm deterministic tie-breaking if duplicate records share
    identical (startTime, publishTime).
    """
    synthetic_duplicates = [
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T07:30:00Z", "generation": 1400},
        {"startTime": "2026-01-05T12:00:00Z", "publishTime": "2026-01-04T07:30:00Z", "generation": 1450},
    ]
    df_syn = normalize_windfor(synthetic_duplicates)
    selected = select_deterministic_vintages(
        windfor_df=df_syn,
        decision_dates=[date(2026, 1, 4)],
        cutoff_time=dt_time(9, 20, 0),
        cutoff_description="EPEX 09:20 Cutoff"
    )

    assert len(selected) == 1
    # Sort order on ["publish_time_utc", "generation_mw"] deterministically yields 1450
    assert selected.iloc[0]["forecast_generation_mw"] == 1450

