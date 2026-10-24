"""
WindSignal Pydantic Schemas
===========================
Response models with timezone-aware UTC timestamps and validated query parameters.
"""

from datetime import datetime, date, time as dt_time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str = Field("healthy", description="Service operational status")
    dataset_ready: bool = Field(..., description="Whether analytical dataset is loaded and ready")
    evaluated_rows: int = Field(..., description="Count of evaluated delivery intervals")
    service_timestamp_utc: datetime = Field(..., description="Current UTC service timestamp")
    version: str = Field("1.0.0", description="API version")


class CutoffConfig(BaseModel):
    cutoff_time_utc: str = Field(..., description="Daily cutoff time in UTC (HH:MM:SS)")
    source_attribution: str = Field(..., description="Market documentation reference")
    is_analytical_assumption: bool = Field(True, description="Whether applicability to utility is an assumption")
    description: str = Field(..., description="Explanation of gate closure and NGESO publication mechanics")


class HeadlineMetrics(BaseModel):
    mean_actual_mw: float = Field(..., description="Average actual wind generation across intervals")
    mae_mw: float = Field(..., description="Mean Absolute Error in MW")
    rmse_mw: float = Field(..., description="Root Mean Squared Error in MW")
    mean_bias_error_mw: float = Field(..., description="Mean Bias Error (positive = overforecast)")
    normalized_mae_pct: float = Field(..., description="MAE as percentage of Mean Actual")
    p90_abs_error_mw: float = Field(..., description="90th percentile of absolute error in MW")
    max_overforecast_mw: float = Field(..., description="Maximum positive forecast error in MW")
    max_underforecast_mw: float = Field(..., description="Maximum negative forecast error in MW")
    bias_direction: str = Field(..., description="'Overforecast' or 'Underforecast'")
    units: Dict[str, str] = Field(..., description="Metric units mapping")


class OverviewResponse(BaseModel):
    decision_window: Dict[str, Any] = Field(..., description="Decision dates scope")
    delivery_window: Dict[str, Any] = Field(..., description="Delivery dates scope and coverage")
    decision_cutoff: CutoffConfig = Field(..., description="Configured decision cutoff details")
    headline_metrics: HeadlineMetrics = Field(..., description="Validated benchmark accuracy metrics")
    sample_counts: Dict[str, int] = Field(..., description="Sample interval counts")


class ForecastVsActualItem(BaseModel):
    delivery_start_time_utc: datetime = Field(..., description="Delivery interval start in UTC")
    delivery_date: date = Field(..., description="Delivery calendar date")
    start_settlement_period: int = Field(..., description="Starting half-hourly settlement period (odd, 1-47)")
    end_settlement_period: int = Field(..., description="Ending half-hourly settlement period (even, 2-48)")
    forecast_generation_mw: float = Field(..., description="Selected day-ahead forecast generation in MW")
    actual_generation_mean_mw: float = Field(..., description="Average outturn generation across both half-hours in MW")
    forecast_error_mw: float = Field(..., description="Signed error = forecast - actual (MW)")
    percentage_error: Optional[float] = Field(None, description="Signed error as % of actual outturn")
    abs_error_mw: float = Field(..., description="Absolute forecast error in MW")
    forecast_publish_time_utc: datetime = Field(..., description="Publication timestamp of chosen vintage")
    lead_time_hours: float = Field(..., description="Lead time from publication to delivery start")


class ForecastVsActualResponse(BaseModel):
    total_records: int = Field(..., description="Number of returned interval records")
    filter_applied: Dict[str, Optional[str]] = Field(..., description="Date filters applied to query")
    data: List[ForecastVsActualItem] = Field(..., description="List of hourly interval comparisons")


class AccuracyMetricsResponse(BaseModel):
    filter_applied: Dict[str, Optional[str]] = Field(..., description="Date filters applied")
    expected_intervals: int = Field(..., description="Expected delivery intervals in filter window")
    matched_intervals: int = Field(..., description="Available matched intervals in dataset")
    coverage_percentage: float = Field(..., description="Percentage of window covered")
    mean_actual_mw: float = Field(..., description="Mean actual generation in MW")
    mae_mw: float = Field(..., description="Mean Absolute Error in MW")
    rmse_mw: float = Field(..., description="Root Mean Squared Error in MW")
    mean_bias_error_mw: float = Field(..., description="Signed bias = mean(forecast - actual) in MW")
    normalized_mae_pct: float = Field(..., description="MAE / Mean Actual (%)")
    p90_abs_error_mw: float = Field(..., description="90th percentile of absolute error in MW")
    max_overforecast_mw: float = Field(..., description="Peak positive error in MW")
    max_underforecast_mw: float = Field(..., description="Peak negative error in MW")
    error_convention: str = Field(
        "forecast - actual (positive = overforecast, negative = underforecast)",
        description="Error formula semantics"
    )
    units: Dict[str, str] = Field(..., description="Measurement units")


class VintageItem(BaseModel):
    publish_time_utc: datetime = Field(..., description="Forecast publication timestamp")
    forecast_generation_mw: float = Field(..., description="Forecasted wind generation in MW")
    is_eligible_prior_to_cutoff: bool = Field(..., description="Whether published on or before decision cutoff")
    is_selected: bool = Field(..., description="Whether this vintage was selected at gate closure")
    latency_to_cutoff_hours: Optional[float] = Field(None, description="Hours between publication and cutoff")
    lead_time_to_delivery_hours: float = Field(..., description="Hours between publication and delivery start")


class ForecastVintagesResponse(BaseModel):
    delivery_start_time_utc: datetime = Field(..., description="Target delivery interval")
    decision_date: date = Field(..., description="Associated decision date (D-1)")
    cutoff_time_utc: datetime = Field(..., description="Exact cutoff timestamp applied")
    cutoff_source: str = Field(..., description="Attribution of market cutoff")
    selected_vintage: Optional[VintageItem] = Field(None, description="Selected vintage without look-ahead bias")
    total_vintages_available: int = Field(..., description="Total historical publication runs found")
    eligible_vintages_count: int = Field(..., description="Vintages published prior to cutoff")
    excluded_vintages_count: int = Field(..., description="Vintages published after cutoff (excluded to prevent look-ahead bias)")
    vintages: List[VintageItem] = Field(..., description="All historical publications for this delivery interval")


class DataQualityResponse(BaseModel):
    audit_timestamp_utc: datetime = Field(..., description="Audit timestamp")
    delivery_window: Dict[str, Any] = Field(..., description="Target delivery boundaries & coverage")
    validation_invariants: Dict[str, Any] = Field(..., description="Automated invariant check results")
    raw_ingestion: Dict[str, Any] = Field(..., description="Raw ingestion metrics & latency")
    error_summary: Dict[str, Any] = Field(..., description="Summary error statistics")
