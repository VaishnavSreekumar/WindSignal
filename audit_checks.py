import json
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PARQUET_FILE = PROJECT_ROOT / "data" / "processed" / "wind_analytical_dataset.parquet"
CSV_FILE = PROJECT_ROOT / "data" / "processed" / "wind_analytical_dataset.csv"
JSON_AUDIT = PROJECT_ROOT / "data" / "processed" / "data_quality_summary.json"
FUELHH_RAW = PROJECT_ROOT / "data" / "raw" / "fuelhh_raw.json"
WINDFOR_RAW = PROJECT_ROOT / "data" / "raw" / "windfor_raw.json"

print("="*80)
print("WINDSIGNAL PHASE 1.1 INDEPENDENT ANALYTICAL AUDIT SCRIPT")
print("="*80)

# 1. Load analytical dataset
df_p = pd.read_parquet(PARQUET_FILE)
df_c = pd.read_csv(CSV_FILE)
with open(JSON_AUDIT, "r", encoding="utf-8") as f:
    audit_json = json.load(f)

print(f"Parquet row count: {len(df_p)}, column count: {len(df_p.columns)}")
print(f"CSV row count:     {len(df_c)}, column count: {len(df_c.columns)}")
print("Columns in analytical dataset:", list(df_p.columns))

# 2. Verify error convention: error = forecast - actual
# Positive: overforecast, Negative: underforecast
diff = df_p["forecast_error_mw"] - (df_p["forecast_generation_mw"] - df_p["actual_generation_mean_mw"])
print(f"Max absolute deviation in forecast_error_mw formula: {diff.abs().max()}")
assert (diff.abs() < 1e-9).all(), "forecast_error_mw does not equal forecast - actual!"

# Check percentage error formula
expected_pct = (df_p["forecast_error_mw"] / df_p["actual_generation_mean_mw"]) * 100.0
pct_diff = (df_p["percentage_error"] - expected_pct).abs().max()
print(f"Max absolute deviation in percentage_error: {pct_diff}")

# 3. Independent metric recomputation
mean_actual = df_p["actual_generation_mean_mw"].mean()
mae = df_p["abs_error_mw"].mean()
rmse = np.sqrt((df_p["forecast_error_mw"]**2).mean())
mbe = df_p["forecast_error_mw"].mean()
nmae = (mae / mean_actual) * 100.0
max_over = df_p["forecast_error_mw"].max()
max_under = df_p["forecast_error_mw"].min()

print("\n--- INDEPENDENT METRIC RECOMPUTATION ---")
print(f"Mean Actual Wind Outturn: {mean_actual:.6f} MW (Reported: {audit_json['error_metrics']['mean_actual_mw']})")
print(f"MAE:                      {mae:.6f} MW (Reported: {audit_json['error_metrics']['mae_mw']})")
print(f"RMSE:                     {rmse:.6f} MW (Reported: {audit_json['error_metrics']['rmse_mw']})")
print(f"MBE (Bias):               {mbe:.6f} MW (Reported: {audit_json['error_metrics']['mean_bias_error_mw']})")
print(f"NMAE (%):                 {nmae:.6f} % (Reported: {audit_json['error_metrics']['normalized_mae_pct']})")
print(f"Max Overforecast:         {max_over:.6f} MW (Reported: {audit_json['error_metrics']['max_overforecast_mw']})")
print(f"Max Underforecast:        {max_under:.6f} MW (Reported: {audit_json['error_metrics']['max_underforecast_mw']})")

# 4. Check Raw FUELHH constituents vs Evaluation dataset
with open(FUELHH_RAW, "r", encoding="utf-8") as f:
    f_data = json.load(f)
fuel_raw = f_data["records"]
df_fuel_raw = pd.DataFrame(fuel_raw)
df_fuel_raw["start_dt"] = pd.to_datetime(df_fuel_raw["startTime"], utc=True)
print(f"\nTotal raw FUELHH records retrieved: {len(df_fuel_raw)}")
print(f"Raw FUELHH date range: {df_fuel_raw['settlementDate'].min()} to {df_fuel_raw['settlementDate'].max()}")

# Filter to intended delivery window: 2026-01-02 to 2026-02-01
fuel_eval = df_fuel_raw[
    (df_fuel_raw["settlementDate"] >= "2026-01-02") &
    (df_fuel_raw["settlementDate"] <= "2026-02-01")
].copy()
print(f"FUELHH records within delivery window (2026-01-02 to 2026-02-01): {len(fuel_eval)}")
print(f"Expected: 31 days * 48 periods = {31 * 48}")
assert len(fuel_eval) == 1488, f"Expected 1488 records, got {len(fuel_eval)}"

# Verify constituent pairing: does hour H always map to SP 2H+1 and 2H+2?
df_fuel_raw["hour_floor"] = df_fuel_raw["start_dt"].dt.floor("h")
fuel_window_grouped = fuel_eval.groupby(fuel_eval["start_dt"].dt.floor("h")).agg(
    sp_count=("settlementPeriod", "count"),
    min_sp=("settlementPeriod", "min"),
    max_sp=("settlementPeriod", "max"),
    mean_gen=("generation", "mean")
).reset_index()

print(f"Grouped hourly delivery periods in window: {len(fuel_window_grouped)}")
assert (fuel_window_grouped["sp_count"] == 2).all(), "Not all hours have exactly 2 SPs!"
assert ((fuel_window_grouped["min_sp"] % 2) != 0).all(), "min_sp not odd!"
assert (fuel_window_grouped["max_sp"] == fuel_window_grouped["min_sp"] + 1).all(), "max_sp not min_sp + 1!"

# Check boundary timestamps
print(f"Delivery window start hour: {fuel_window_grouped['start_dt'].min()}")
print(f"Delivery window end hour:   {fuel_window_grouped['start_dt'].max()}")

# 5. Check WINDFOR raw publications
with open(WINDFOR_RAW, "r", encoding="utf-8") as f:
    w_data = json.load(f)
wind_raw = w_data["records"]
df_wind_raw = pd.DataFrame(wind_raw)
df_wind_raw["pub_dt"] = pd.to_datetime(df_wind_raw["publishTime"], utc=True)
df_wind_raw["start_dt"] = pd.to_datetime(df_wind_raw["startTime"], utc=True)

print(f"\nTotal raw WINDFOR records retrieved: {len(df_wind_raw)}")
print(f"Raw WINDFOR publish range: {df_wind_raw['pub_dt'].min()} to {df_wind_raw['pub_dt'].max()}")
print(f"Raw WINDFOR start range:   {df_wind_raw['start_dt'].min()} to {df_wind_raw['start_dt'].max()}")

# Check all distinct publish times used in analytical dataset
pub_times_used = pd.to_datetime(df_p["forecast_publish_time_utc"]).dt.time.value_counts().to_dict()
print(f"Publish times used in analytical dataset for 09:20 cutoff: {pub_times_used}")

# Check look-ahead violations
cutoff_dt = pd.to_datetime(df_p["cutoff_time_utc"])
pub_dt = pd.to_datetime(df_p["forecast_publish_time_utc"])
violations = (pub_dt > cutoff_dt).sum()
print(f"Total look-ahead violations: {violations}")

# Check lead time
del_dt = pd.to_datetime(df_p["delivery_start_time_utc"])
min_lead = (del_dt - pub_dt).dt.total_seconds() / 3600.0
print(f"Lead time range: min={min_lead.min():.1f}h, max={min_lead.max():.1f}h, mean={min_lead.mean():.1f}h")

# Check vintage latency (cutoff - publish)
cutoff_latency = (cutoff_dt - pub_dt).dt.total_seconds() / 3600.0
print(f"Cutoff latency range: min={cutoff_latency.min():.1f}h, max={cutoff_latency.max():.1f}h, mean={cutoff_latency.mean():.1f}h")
