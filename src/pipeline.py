"""
WindSignal Data Pipeline Core Module
====================================
Provides ingestion, validation, timestamp normalization, half-hourly-to-hourly
aggregation, deterministic vintage selection without look-ahead bias, and
data-quality auditing for Elexon BMRS FUELHH and WINDFOR streams.
"""

from datetime import datetime, date, time as dt_time, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
import json
import os
import requests
import pandas as pd
import numpy as np

# Official Elexon Insights Solution Base URL
ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
USER_AGENT = "WindSignal-Pipeline/1.0 (Day-Ahead Renewable Procurement Analytics)"


class PipelineException(Exception):
    """Custom exception raised for pipeline data validation or API errors."""
    pass


def fetch_fuelhh_stream(
    settlement_date_from: str,
    settlement_date_to: str,
    fuel_type: str = "WIND",
    cache_path: Optional[str] = None,
    force_fetch: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch actual half-hourly outturn generation from /datasets/FUELHH/stream.
    
    Parameters
    ----------
    settlement_date_from : str
        Start settlement date in YYYY-MM-DD.
    settlement_date_to : str
        End settlement date in YYYY-MM-DD.
    fuel_type : str
        Fuel type filter (default "WIND").
    cache_path : Optional[str]
        File path to save/load raw JSON.
    force_fetch : bool
        If True, ignores existing cache and re-fetches.
        
    Returns
    -------
    Tuple[List[Dict[str, Any]], Dict[str, Any]]
        (raw_records, metadata)
    """
    if cache_path and os.path.exists(cache_path) and not force_fetch:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
            return cached["records"], cached["metadata"]

    endpoint = f"{ELEXON_BASE_URL}/datasets/FUELHH/stream"
    params = {
        "settlementDateFrom": settlement_date_from,
        "settlementDateTo": settlement_date_to,
        "fuelType": fuel_type
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    req_start = datetime.now(timezone.utc)
    response = requests.get(endpoint, params=params, headers=headers, timeout=60)
    req_end = datetime.now(timezone.utc)

    if response.status_code != 200:
        raise PipelineException(
            f"Failed to fetch FUELHH stream: HTTP {response.status_code} - {response.text[:200]}"
        )

    records = response.json()
    metadata = {
        "dataset": "FUELHH",
        "endpoint": endpoint,
        "url_requested": response.url,
        "params": params,
        "retrieval_timestamp_utc": req_start.isoformat(),
        "elapsed_seconds": (req_end - req_start).total_seconds(),
        "http_status": response.status_code,
        "record_count": len(records),
        "content_type": response.headers.get("Content-Type")
    }

    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"metadata": metadata, "records": records}, f, indent=2)

    return records, metadata


def fetch_windfor_stream(
    publish_datetime_from: str,
    publish_datetime_to: str,
    cache_path: Optional[str] = None,
    force_fetch: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetch historical wind forecast publications from /datasets/WINDFOR/stream.
    
    Parameters
    ----------
    publish_datetime_from : str
        Start publication timestamp in ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ).
    publish_datetime_to : str
        End publication timestamp in ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ).
    cache_path : Optional[str]
        File path to save/load raw JSON.
    force_fetch : bool
        If True, ignores existing cache and re-fetches.
        
    Returns
    -------
    Tuple[List[Dict[str, Any]], Dict[str, Any]]
        (raw_records, metadata)
    """
    if cache_path and os.path.exists(cache_path) and not force_fetch:
        with open(cache_path, "r", encoding="utf-8") as f:
            cached = json.load(f)
            return cached["records"], cached["metadata"]

    endpoint = f"{ELEXON_BASE_URL}/datasets/WINDFOR/stream"
    params = {
        "publishDateTimeFrom": publish_datetime_from,
        "publishDateTimeTo": publish_datetime_to
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    req_start = datetime.now(timezone.utc)
    response = requests.get(endpoint, params=params, headers=headers, timeout=90)
    req_end = datetime.now(timezone.utc)

    if response.status_code != 200:
        raise PipelineException(
            f"Failed to fetch WINDFOR stream: HTTP {response.status_code} - {response.text[:200]}"
        )

    records = response.json()
    metadata = {
        "dataset": "WINDFOR",
        "endpoint": endpoint,
        "url_requested": response.url,
        "params": params,
        "retrieval_timestamp_utc": req_start.isoformat(),
        "elapsed_seconds": (req_end - req_start).total_seconds(),
        "http_status": response.status_code,
        "record_count": len(records),
        "content_type": response.headers.get("Content-Type")
    }

    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"metadata": metadata, "records": records}, f, indent=2)

    return records, metadata


def validate_raw_records(records: List[Dict[str, Any]], dataset_type: str) -> Dict[str, Any]:
    """
    Validate raw records for required fields, numeric generation, and nulls.
    """
    audit = {
        "dataset_type": dataset_type,
        "total_records": len(records),
        "null_start_time": 0,
        "null_publish_time": 0,
        "non_numeric_generation": 0,
        "negative_generation": 0,
        "valid_records": 0
    }
    for r in records:
        st = r.get("startTime")
        pt = r.get("publishTime")
        gen = r.get("generation")

        if not st:
            audit["null_start_time"] += 1
            continue
        if not pt:
            audit["null_publish_time"] += 1
            continue
        if gen is None or not isinstance(gen, (int, float)):
            audit["non_numeric_generation"] += 1
            continue
        if gen < 0:
            audit["negative_generation"] += 1
            continue

        audit["valid_records"] += 1

    return audit


def normalize_fuelhh(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize FUELHH actuals to a clean DataFrame with normalized UTC timestamps.
    """
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=[
            "dataset", "raw_publish_time", "raw_start_time", "publish_time_utc",
            "start_time_utc", "settlement_date", "settlement_period", "fuel_type",
            "generation_mw"
        ])

    df = df.rename(columns={
        "publishTime": "raw_publish_time",
        "startTime": "raw_start_time",
        "settlementDate": "settlement_date",
        "settlementPeriod": "settlement_period",
        "fuelType": "fuel_type",
        "generation": "generation_mw"
    })

    # Strict UTC parsing
    df["start_time_utc"] = pd.to_datetime(df["raw_start_time"], utc=True)
    df["publish_time_utc"] = pd.to_datetime(df["raw_publish_time"], utc=True)
    df["generation_mw"] = pd.to_numeric(df["generation_mw"], errors="coerce")
    df["settlement_period"] = df["settlement_period"].astype(int)

    # Sort deterministically
    df = df.sort_values(["start_time_utc", "settlement_period"]).reset_index(drop=True)
    return df


def normalize_windfor(records: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize WINDFOR forecasts to a clean DataFrame with normalized UTC timestamps.
    """
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=[
            "dataset", "raw_publish_time", "raw_start_time", "publish_time_utc",
            "start_time_utc", "generation_mw"
        ])

    df = df.rename(columns={
        "publishTime": "raw_publish_time",
        "startTime": "raw_start_time",
        "generation": "generation_mw"
    })

    df["start_time_utc"] = pd.to_datetime(df["raw_start_time"], utc=True)
    df["publish_time_utc"] = pd.to_datetime(df["raw_publish_time"], utc=True)
    df["generation_mw"] = pd.to_numeric(df["generation_mw"], errors="coerce")

    # Sort deterministically
    df = df.sort_values(["start_time_utc", "publish_time_utc"]).reset_index(drop=True)
    return df


def aggregate_fuelhh_to_hourly(fuelhh_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate half-hourly FUELHH actuals to 60-minute delivery intervals to match
    WINDFOR forecast resolution.
    
    Settlement Periods are paired:
    Hour 00:00 -> SP 1 (00:00-00:30) and SP 2 (00:30-01:00)
    Hour 01:00 -> SP 3 (01:00-01:30) and SP 4 (01:30-02:00)
    ...
    Hour 23:00 -> SP 47 (23:00-23:30) and SP 48 (23:30-24:00)
    """
    if fuelhh_df.empty:
        return pd.DataFrame()

    df = fuelhh_df.copy()
    # Floor to top of hour
    df["hourly_delivery_start_utc"] = df["start_time_utc"].dt.floor("h")

    # Explicitly separate odd (SP1) and even (SP2) settlement periods
    df["sp1_mw"] = np.where(df["settlement_period"] % 2 != 0, df["generation_mw"], np.nan)
    df["sp2_mw"] = np.where(df["settlement_period"] % 2 == 0, df["generation_mw"], np.nan)

    # Aggregate by top of hour
    grouped = df.groupby("hourly_delivery_start_utc").agg(
        delivery_date=("settlement_date", "first"),
        start_settlement_period=("settlement_period", "min"),
        end_settlement_period=("settlement_period", "max"),
        period_count=("generation_mw", "count"),
        actual_generation_mean_mw=("generation_mw", "mean"),
        actual_generation_min_mw=("generation_mw", "min"),
        actual_generation_max_mw=("generation_mw", "max"),
        actual_generation_sp1_mw=("sp1_mw", "min"),  # min ignores NaN
        actual_generation_sp2_mw=("sp2_mw", "min"),  # min ignores NaN
        latest_publish_time_utc=("publish_time_utc", "max")
    ).reset_index()

    # Integrity verification: every hour should have exactly 2 settlement periods
    grouped["is_complete_hour"] = (
        (grouped["period_count"] == 2) &
        (grouped["start_settlement_period"] % 2 != 0) &
        (grouped["end_settlement_period"] == grouped["start_settlement_period"] + 1)
    )
    return grouped


def select_deterministic_vintages(
    windfor_df: pd.DataFrame,
    decision_dates: List[date],
    cutoff_time: dt_time = dt_time(9, 20, 0),
    cutoff_description: str = "EPEX SPOT GB 60-minute Day-Ahead Auction Gate Closure (09:20 GMT/BST)"
) -> pd.DataFrame:
    """
    Select the deterministic latest wind forecast vintage available at or before
    the decision cutoff for each target delivery hour, strictly eliminating look-ahead bias.
    
    Parameters
    ----------
    windfor_df : pd.DataFrame
        Normalized WINDFOR DataFrame.
    decision_dates : List[date]
        List of decision dates (D_dec). The corresponding delivery date is D_dec + 1 day.
    cutoff_time : dt_time
        Time of day cutoff (default 09:20:00).
    cutoff_description : str
        Human-readable attribution of the cutoff.
        
    Returns
    -------
    pd.DataFrame
        Selected forecasts for each delivery hour.
    """
    if windfor_df.empty:
        return pd.DataFrame()

    results = []

    for d_dec in decision_dates:
        d_del = d_dec + timedelta(days=1)
        cutoff_dt_utc = datetime.combine(d_dec, cutoff_time, tzinfo=timezone.utc)

        # Target intervals: all 24 hours of delivery date d_del (00:00:00Z to 23:00:00Z)
        d_del_start = datetime.combine(d_del, dt_time(0, 0, 0), tzinfo=timezone.utc)
        d_del_end = datetime.combine(d_del, dt_time(23, 0, 0), tzinfo=timezone.utc)

        # Slice all forecasts targeting d_del
        target_fc = windfor_df[
            (windfor_df["start_time_utc"] >= d_del_start) &
            (windfor_df["start_time_utc"] <= d_del_end)
        ].copy()

        # Filter strictly for publications at or prior to cutoff
        valid_vintages = target_fc[target_fc["publish_time_utc"] <= cutoff_dt_utc].copy()

        # Group by target delivery hour and select the maximum publish_time_utc
        # (the latest information available to the trader prior to gate closure)
        for target_st, group in valid_vintages.groupby("start_time_utc"):
            latest_record = group.sort_values(["publish_time_utc", "generation_mw"]).iloc[-1]

            results.append({
                "decision_date": d_dec.isoformat(),
                "delivery_date": d_del.isoformat(),
                "cutoff_time_utc": cutoff_dt_utc.isoformat(),
                "cutoff_source": cutoff_description,
                "delivery_start_time_utc": target_st,
                "forecast_publish_time_utc": latest_record["publish_time_utc"],
                "raw_publish_time": latest_record["raw_publish_time"],
                "raw_start_time": latest_record["raw_start_time"],
                "forecast_generation_mw": latest_record["generation_mw"],
                "available_vintages_count": len(group),
                "vintage_latency_hours": (cutoff_dt_utc - latest_record["publish_time_utc"]).total_seconds() / 3600.0,
                "lead_time_hours": (target_st - latest_record["publish_time_utc"]).total_seconds() / 3600.0
            })

    selected_df = pd.DataFrame(results)
    if not selected_df.empty:
        selected_df = selected_df.sort_values("delivery_start_time_utc").reset_index(drop=True)
    return selected_df


def build_analytical_dataset(
    selected_forecasts_df: pd.DataFrame,
    hourly_actuals_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge selected day-ahead forecasts with hourly aggregated actual generation.
    Computes absolute error, signed error, and percentage error without look-ahead bias.
    """
    if selected_forecasts_df.empty or hourly_actuals_df.empty:
        return pd.DataFrame()

    # Drop duplicate delivery_date from hourly_actuals_df to prevent _x/_y suffix
    actuals_clean = hourly_actuals_df.copy()
    if "delivery_date" in actuals_clean.columns and "delivery_date" in selected_forecasts_df.columns:
        actuals_clean = actuals_clean.drop(columns=["delivery_date"])

    merged = pd.merge(
        selected_forecasts_df,
        actuals_clean,
        left_on="delivery_start_time_utc",
        right_on="hourly_delivery_start_utc",
        how="inner"
    )

    # Compute Error Metrics
    # Positive error: Overforecast (Forecast > Actual)
    # Negative error: Underforecast (Forecast < Actual)
    merged["forecast_error_mw"] = merged["forecast_generation_mw"] - merged["actual_generation_mean_mw"]
    merged["abs_error_mw"] = merged["forecast_error_mw"].abs()
    
    # Avoid zero division
    merged["percentage_error"] = np.where(
        merged["actual_generation_mean_mw"] > 0,
        (merged["forecast_error_mw"] / merged["actual_generation_mean_mw"]) * 100.0,
        np.nan
    )
    merged["abs_percentage_error"] = merged["percentage_error"].abs()

    # Reorder columns cleanly
    cols_order = [
        "decision_date",
        "delivery_date",
        "delivery_start_time_utc",
        "start_settlement_period",
        "end_settlement_period",
        "cutoff_time_utc",
        "cutoff_source",
        "forecast_publish_time_utc",
        "lead_time_hours",
        "forecast_generation_mw",
        "actual_generation_mean_mw",
        "actual_generation_sp1_mw",
        "actual_generation_sp2_mw",
        "forecast_error_mw",
        "abs_error_mw",
        "percentage_error",
        "abs_percentage_error",
        "available_vintages_count",
        "vintage_latency_hours"
    ]
    
    # Keep any extra columns at the end
    existing_cols = [c for c in cols_order if c in merged.columns]
    extra_cols = [c for c in merged.columns if c not in cols_order]
    return merged[existing_cols + extra_cols].sort_values("delivery_start_time_utc").reset_index(drop=True)


def generate_data_quality_audit(
    raw_fuelhh_meta: Dict[str, Any],
    raw_windfor_meta: Dict[str, Any],
    raw_fuelhh_audit: Dict[str, Any],
    raw_windfor_audit: Dict[str, Any],
    fuelhh_df: pd.DataFrame,
    windfor_df: pd.DataFrame,
    hourly_actuals_df: pd.DataFrame,
    selected_forecasts_df: pd.DataFrame,
    analytical_df: pd.DataFrame,
    expected_delivery_hours: int
) -> Dict[str, Any]:
    """
    Produce a machine-readable data quality audit dictionary.
    """
    # Look-ahead bias check
    look_ahead_violations = 0
    if not selected_forecasts_df.empty:
        cutoff_series = pd.to_datetime(selected_forecasts_df["cutoff_time_utc"])
        pub_series = pd.to_datetime(selected_forecasts_df["forecast_publish_time_utc"])
        look_ahead_violations = int((pub_series > cutoff_series).sum())

    # Duplicate checks
    fuelhh_dups = int(fuelhh_df.duplicated(subset=["start_time_utc", "fuel_type"]).sum())
    windfor_dups = int(windfor_df.duplicated(subset=["start_time_utc", "publish_time_utc"]).sum())
    analytical_dups = int(analytical_df.duplicated(subset=["delivery_start_time_utc"]).sum())

    # Missing interval calculation
    reconstructed_count = len(analytical_df)
    missing_count = max(0, expected_delivery_hours - reconstructed_count)

    # Statistical summary of generation & error
    mae = float(analytical_df["abs_error_mw"].mean()) if not analytical_df.empty else 0.0
    rmse = float(np.sqrt((analytical_df["forecast_error_mw"]**2).mean())) if not analytical_df.empty else 0.0
    mbe = float(analytical_df["forecast_error_mw"].mean()) if not analytical_df.empty else 0.0
    mean_actual = float(analytical_df["actual_generation_mean_mw"].mean()) if not analytical_df.empty else 0.0
    nmae = float((mae / mean_actual) * 100.0) if mean_actual > 0 else 0.0

    return {
        "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "delivery_window": {
            "start": analytical_df["delivery_start_time_utc"].min().isoformat() if not analytical_df.empty else None,
            "end": analytical_df["delivery_start_time_utc"].max().isoformat() if not analytical_df.empty else None,
            "expected_delivery_hours": expected_delivery_hours,
            "covered_delivery_hours": reconstructed_count,
            "missing_delivery_hours": missing_count,
            "coverage_percentage": (reconstructed_count / expected_delivery_hours) * 100.0 if expected_delivery_hours > 0 else 0.0
        },
        "raw_ingestion": {
            "fuelhh": raw_fuelhh_meta,
            "windfor": raw_windfor_meta
        },
        "validation_invariants": {
            "look_ahead_violations": look_ahead_violations,
            "fuelhh_duplicates": fuelhh_dups,
            "windfor_duplicates": windfor_dups,
            "analytical_dataset_duplicates": analytical_dups,
            "negative_actual_generation_count": int((fuelhh_df["generation_mw"] < 0).sum()) if not fuelhh_df.empty else 0,
            "negative_forecast_generation_count": int((windfor_df["generation_mw"] < 0).sum()) if not windfor_df.empty else 0,
            "hourly_aggregation_period_integrity": bool((hourly_actuals_df["period_count"] == 2).all()) if not hourly_actuals_df.empty else False
        },
        "error_metrics": {
            "mean_actual_mw": round(mean_actual, 2),
            "mae_mw": round(mae, 2),
            "rmse_mw": round(rmse, 2),
            "mean_bias_error_mw": round(mbe, 2),
            "normalized_mae_pct": round(nmae, 2),
            "max_overforecast_mw": round(float(analytical_df["forecast_error_mw"].max()), 2) if not analytical_df.empty else 0.0,
            "max_underforecast_mw": round(float(analytical_df["forecast_error_mw"].min()), 2) if not analytical_df.empty else 0.0
        }
    }
