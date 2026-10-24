/**
 * WindSignal API Type Definitions
 * Exact mirrors of FastAPI Pydantic schemas in src/schemas.py.
 */

export interface HealthResponse {
  status: string;
  dataset_ready: boolean;
  evaluated_rows: number;
  service_timestamp_utc: string;
  version: string;
}

export interface CutoffConfig {
  cutoff_time_utc: string;
  source_attribution: string;
  is_analytical_assumption: boolean;
  description: string;
}

export interface HeadlineMetrics {
  mean_actual_mw: number;
  mae_mw: number;
  rmse_mw: number;
  mean_bias_error_mw: number;
  normalized_mae_pct: number;
  p90_abs_error_mw: number;
  max_overforecast_mw: number;
  max_underforecast_mw: number;
  bias_direction: string;
  units: Record<string, string>;
}

export interface OverviewResponse {
  decision_window: {
    start_date: string;
    end_date: string;
    total_days: number;
  };
  delivery_window: {
    start_datetime_utc: string;
    end_datetime_utc: string;
    total_hours: number;
    expected_hours: number;
    coverage_percentage: number;
  };
  decision_cutoff: CutoffConfig;
  headline_metrics: HeadlineMetrics;
  sample_counts: {
    evaluated_intervals: number;
    constituent_half_hourly_observations: number;
  };
}

export interface ForecastVsActualItem {
  delivery_start_time_utc: string;
  delivery_date: string;
  start_settlement_period: number;
  end_settlement_period: number;
  forecast_generation_mw: number;
  actual_generation_mean_mw: number;
  forecast_error_mw: number;
  percentage_error: number | null;
  abs_error_mw: number;
  forecast_publish_time_utc: string;
  lead_time_hours: number;
}

export interface ForecastVsActualResponse {
  total_records: number;
  filter_applied: {
    delivery_date_from: string | null;
    delivery_date_to: string | null;
  };
  data: ForecastVsActualItem[];
}

export interface AccuracyMetricsResponse {
  filter_applied: {
    delivery_date_from: string | null;
    delivery_date_to: string | null;
  };
  expected_intervals: number;
  matched_intervals: number;
  coverage_percentage: number;
  mean_actual_mw: number;
  mae_mw: number;
  rmse_mw: number;
  mean_bias_error_mw: number;
  normalized_mae_pct: number;
  p90_abs_error_mw: number;
  max_overforecast_mw: number;
  max_underforecast_mw: number;
  error_convention: string;
  units: Record<string, string>;
}

export interface VintageItem {
  publish_time_utc: string;
  forecast_generation_mw: number;
  is_eligible_prior_to_cutoff: boolean;
  is_selected: boolean;
  latency_to_cutoff_hours: number | null;
  lead_time_to_delivery_hours: number;
}

export interface ForecastVintagesResponse {
  delivery_start_time_utc: string;
  decision_date: string;
  cutoff_time_utc: string;
  cutoff_source: string;
  selected_vintage: VintageItem | null;
  total_vintages_available: number;
  eligible_vintages_count: number;
  excluded_vintages_count: number;
  vintages: VintageItem[];
}

export interface DataQualityResponse {
  audit_timestamp_utc: string;
  delivery_window: {
    start: string;
    end: string;
    expected_delivery_hours: number;
    covered_delivery_hours: number;
    missing_delivery_hours: number;
    coverage_percentage: number;
  };
  validation_invariants: {
    look_ahead_violations: number;
    fuelhh_duplicates: number;
    windfor_duplicates: number;
    analytical_dataset_duplicates: number;
    negative_actual_generation_count: number;
    negative_forecast_generation_count: number;
    hourly_aggregation_period_integrity: boolean;
    all_invariants_passed: boolean;
  };
  raw_ingestion: {
    fuelhh_record_count: number;
    windfor_record_count: number;
    fuelhh_latency_s: number;
    windfor_latency_s: number;
  };
  error_summary: {
    mean_actual_mw: number;
    mae_mw: number;
    rmse_mw: number;
    mean_bias_error_mw: number;
    normalized_mae_pct: number;
    max_overforecast_mw: number;
    max_underforecast_mw: number;
  };
}
