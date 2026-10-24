"""
Integration Tests for WindSignal FastAPI Backend
================================================
Validates all endpoints, dynamic recalculation, vintage selection,
filter edge cases, CSV exports, and audited metric consistency.
"""

import sys
from pathlib import Path
from datetime import datetime, date, timezone
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api import app, service


@pytest.fixture(scope="session", autouse=True)
def initialize_service():
    """Ensure service dataset is loaded before tests execute."""
    service.load_data()


@pytest.fixture(scope="session")
def client():
    """Create FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client


# -------------------------------------------------------------------------
# 1. Health and Dataset Readiness
# -------------------------------------------------------------------------

def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["dataset_ready"] is True
    assert data["evaluated_rows"] == 744
    assert "version" in data
    assert "service_timestamp_utc" in data

    # Security check: Ensure local filesystem paths or secrets are not leaked
    body_str = response.text.lower()
    assert "c:\\" not in body_str
    assert "scratch" not in body_str
    assert "users" not in body_str


# -------------------------------------------------------------------------
# 2. Overview Metrics & Reference Consistency
# -------------------------------------------------------------------------

def test_overview_endpoint_metrics_consistency(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()

    # Decision & Delivery window checks
    dw = data["decision_window"]
    del_w = data["delivery_window"]
    assert dw["start_date"] == "2026-01-01"
    assert dw["end_date"] == "2026-01-31"
    assert dw["total_days"] == 31

    assert del_w["total_hours"] == 744
    assert del_w["expected_hours"] == 744
    assert del_w["coverage_percentage"] == 100.0

    # Decision cutoff documentation & assumption check
    cutoff = data["decision_cutoff"]
    assert cutoff["cutoff_time_utc"] == "09:20:00"
    assert "EPEX SPOT" in cutoff["source_attribution"]
    assert cutoff["is_analytical_assumption"] is True

    # Audit benchmark reference values reproduction (floating-point tolerance < 0.05)
    hm = data["headline_metrics"]
    assert pytest.approx(hm["mean_actual_mw"], abs=0.1) == 11283.56
    assert pytest.approx(hm["mae_mw"], abs=0.1) == 2038.91
    assert pytest.approx(hm["rmse_mw"], abs=0.1) == 2504.76
    assert pytest.approx(hm["mean_bias_error_mw"], abs=0.1) == 1747.89
    assert pytest.approx(hm["normalized_mae_pct"], abs=0.05) == 18.07
    assert pytest.approx(hm["p90_abs_error_mw"], abs=0.1) == 4097.90
    assert pytest.approx(hm["max_overforecast_mw"], abs=0.1) == 6870.0
    assert pytest.approx(hm["max_underforecast_mw"], abs=0.1) == -3550.0
    assert hm["bias_direction"] == "Overforecast"

    # Sample counts
    sc = data["sample_counts"]
    assert sc["evaluated_intervals"] == 744
    assert sc["constituent_half_hourly_observations"] == 1488


# -------------------------------------------------------------------------
# 3. Forecast vs. Actual Time-Series
# -------------------------------------------------------------------------

def test_forecast_vs_actual_full_window(client):
    response = client.get("/api/forecast-vs-actual")
    assert response.status_code == 200
    data = response.json()

    assert data["total_records"] == 744
    records = data["data"]
    assert len(records) == 744

    # Check first record properties
    first = records[0]
    assert first["delivery_date"] == "2026-01-02"
    assert "delivery_start_time_utc" in first
    assert "forecast_generation_mw" in first
    assert "actual_generation_mean_mw" in first
    assert "forecast_error_mw" in first
    assert first["start_settlement_period"] == 1
    assert first["end_settlement_period"] == 2

    # Verify error convention: error = forecast - actual
    expected_error = first["forecast_generation_mw"] - first["actual_generation_mean_mw"]
    assert pytest.approx(first["forecast_error_mw"], abs=1e-4) == expected_error


def test_forecast_vs_actual_date_filtering(client):
    # Filter 3 days: 2026-01-05 to 2026-01-07 (72 hours)
    response = client.get(
        "/api/forecast-vs-actual",
        params={"delivery_date_from": "2026-01-05", "delivery_date_to": "2026-01-07"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 72
    for item in data["data"]:
        assert "2026-01-05" <= item["delivery_date"] <= "2026-01-07"


def test_forecast_vs_actual_empty_filter_result(client):
    # Filter for future date with no records in dataset
    response = client.get(
        "/api/forecast-vs-actual",
        params={"delivery_date_from": "2026-03-01", "delivery_date_to": "2026-03-05"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 0
    assert data["data"] == []


def test_forecast_vs_actual_invalid_date_range(client):
    # from > to should return 400 Bad Request
    response = client.get(
        "/api/forecast-vs-actual",
        params={"delivery_date_from": "2026-01-10", "delivery_date_to": "2026-01-05"}
    )
    assert response.status_code == 400
    assert "cannot be after" in response.json()["detail"]


# -------------------------------------------------------------------------
# 4. Accuracy Metrics & Dynamic Recalculation
# -------------------------------------------------------------------------

def test_accuracy_metrics_full_window(client):
    response = client.get("/api/accuracy")
    assert response.status_code == 200
    data = response.json()

    assert data["expected_intervals"] == 744
    assert data["matched_intervals"] == 744
    assert data["coverage_percentage"] == 100.0

    # Verify audited metrics
    assert pytest.approx(data["mae_mw"], abs=0.1) == 2038.91
    assert pytest.approx(data["rmse_mw"], abs=0.1) == 2504.76
    assert pytest.approx(data["mean_bias_error_mw"], abs=0.1) == 1747.89
    assert pytest.approx(data["p90_abs_error_mw"], abs=0.1) == 4097.90
    assert data["p90_abs_error_mw"] > data["mae_mw"]  # P90 must exceed MAE


def test_p90_metric_exact_definition_and_quantile_method(client):
    """
    Regression Test: P90 Absolute Error Discrepancy Resolution
    Confirms that:
    1. /api/overview and /api/accuracy return the exact same P90 value (4,097.90 MW).
    2. P90 represents the 90th percentile of abs_error_mw using linear quantile interpolation.
    3. Exactly 10% (74-75 intervals) of the 744 evaluated intervals exceed P90.
    """
    resp_ov = client.get("/api/overview")
    resp_acc = client.get("/api/accuracy")
    assert resp_ov.status_code == 200
    assert resp_acc.status_code == 200

    p90_ov = resp_ov.json()["headline_metrics"]["p90_abs_error_mw"]
    p90_acc = resp_acc.json()["p90_abs_error_mw"]

    # Must be strictly identical across endpoints
    assert p90_ov == p90_acc == 4097.90

    # Verify against full time-series data
    resp_ts = client.get("/api/forecast-vs-actual")
    assert resp_ts.status_code == 200
    ts_data = resp_ts.json()["data"]
    abs_errors = sorted([row["abs_error_mw"] for row in ts_data])
    assert len(abs_errors) == 744

    # Count rows strictly greater than P90 (elements with rank > 668.7, so indices 669..743 = 75 items)
    exceedances = [e for e in abs_errors if e > p90_acc]
    assert len(exceedances) == 75
    # All values up to rank 668 are <= 4097.90 MW, and rank 669 is >= 4097.90 MW
    assert abs_errors[668] <= 4097.90 <= abs_errors[669]


def test_accuracy_metrics_filtered_recalculation(client):
    # Single day filter: 2026-01-15 (24 hours)
    response = client.get(
        "/api/accuracy",
        params={"delivery_date_from": "2026-01-15", "delivery_date_to": "2026-01-15"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["expected_intervals"] == 24
    assert data["matched_intervals"] == 24
    assert data["coverage_percentage"] == 100.0

    # Ensure metrics are dynamically recalculated, NOT static full-window copies
    assert data["mae_mw"] != 2038.91
    assert data["mae_mw"] > 0
    assert data["rmse_mw"] > 0


def test_accuracy_metrics_empty_window(client):
    response = client.get(
        "/api/accuracy",
        params={"delivery_date_from": "2026-05-01", "delivery_date_to": "2026-05-02"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched_intervals"] == 0
    assert data["mae_mw"] == 0.0
    assert data["coverage_percentage"] == 0.0


# -------------------------------------------------------------------------
# 5. Forecast Vintages & Look-Ahead Exclusion
# -------------------------------------------------------------------------

def test_forecast_vintages_valid_interval(client):
    target_dt = "2026-01-02T12:00:00Z"
    response = client.get(
        "/api/forecast-vintages",
        params={"delivery_start_time": target_dt}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["delivery_start_time_utc"].startswith("2026-01-02T12:00:00")
    assert data["decision_date"] == "2026-01-01"
    assert data["cutoff_time_utc"].startswith("2026-01-01T09:20:00")
    assert data["total_vintages_available"] == 24
    assert data["eligible_vintages_count"] > 0
    assert data["excluded_vintages_count"] > 0

    # Verify selected vintage: must be the 07:30 UTC publication on 2026-01-01
    selected = data["selected_vintage"]
    assert selected is not None
    assert selected["is_selected"] is True
    assert selected["is_eligible_prior_to_cutoff"] is True
    assert "2026-01-01T07:30:00" in selected["publish_time_utc"]

    # Verify strict no-look-ahead rule: no excluded vintage can ever be selected
    for v in data["vintages"]:
        if not v["is_eligible_prior_to_cutoff"]:
            assert v["is_selected"] is False, "A post-cutoff vintage was selected!"


def test_forecast_vintages_invalid_timestamp(client):
    response = client.get(
        "/api/forecast-vintages",
        params={"delivery_start_time": "invalid-timestamp"}
    )
    assert response.status_code == 400
    assert "Invalid timestamp format" in response.json()["detail"]


def test_forecast_vintages_not_found(client):
    # Valid ISO format but interval has no data in raw records
    response = client.get(
        "/api/forecast-vintages",
        params={"delivery_start_time": "2027-01-01T00:00:00Z"}
    )
    assert response.status_code == 404
    assert "No historical WINDFOR publications found" in response.json()["detail"]


# -------------------------------------------------------------------------
# 6. Data Quality Audit Endpoint
# -------------------------------------------------------------------------

def test_data_quality_endpoint(client):
    response = client.get("/api/data-quality")
    assert response.status_code == 200
    data = response.json()

    inv = data["validation_invariants"]
    assert inv["look_ahead_violations"] == 0
    assert inv["analytical_dataset_duplicates"] == 0
    assert inv["hourly_aggregation_period_integrity"] is True
    assert inv["negative_actual_generation_count"] == 0
    assert inv["negative_forecast_generation_count"] == 0
    assert inv["all_invariants_passed"] is True

    raw = data["raw_ingestion"]
    assert raw["fuelhh_record_count"] == 1584
    assert raw["windfor_record_count"] == 19272


# -------------------------------------------------------------------------
# 7. CSV Export Endpoint
# -------------------------------------------------------------------------

def test_csv_export_endpoint(client):
    response = client.get("/api/export.csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert 'attachment; filename="windsignal_forecast_vs_actual.csv"' in response.headers.get("content-disposition", "")

    lines = response.text.strip().split("\r\n")
    if len(lines) == 1:
        lines = response.text.strip().split("\n")

    # Header check
    header = lines[0].split(",")
    assert "delivery_start_time_utc" in header
    assert "forecast_generation_mw" in header
    assert "actual_generation_mean_mw" in header
    assert "forecast_error_mw" in header

    # Row count: 1 header + 744 data rows = 745 lines
    assert len(lines) == 745


def test_csv_export_filtered(client):
    response = client.get(
        "/api/export.csv",
        params={"delivery_date_from": "2026-01-05", "delivery_date_to": "2026-01-06"}
    )
    assert response.status_code == 200
    lines = response.text.strip().split("\r\n")
    if len(lines) == 1:
        lines = response.text.strip().split("\n")

    # 1 header + 48 rows = 49 lines
    assert len(lines) == 49
    assert "2026-01-05_2026-01-06" in response.headers.get("content-disposition", "")


# -------------------------------------------------------------------------
# 8. CORS Preflight & Headers
# -------------------------------------------------------------------------

def test_cors_headers(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
