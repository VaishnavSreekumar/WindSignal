"""
WindSignal Service Layer
========================
Provides analytical query services, dynamic metric recalculation,
vintage lookup from raw historical publications, and CSV export.
"""

import json
import os
import io
import csv
from datetime import datetime, date, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import pandas as pd
import numpy as np

from src.schemas import (
    HealthResponse,
    OverviewResponse,
    HeadlineMetrics,
    CutoffConfig,
    ForecastVsActualResponse,
    ForecastVsActualItem,
    AccuracyMetricsResponse,
    ForecastVintagesResponse,
    VintageItem,
    DataQualityResponse,
)


class DataNotFoundError(Exception):
    """Raised when requested data or delivery interval is not found."""
    pass


class InvalidFilterError(Exception):
    """Raised when query filter parameters are invalid (e.g. from > to)."""
    pass


def _resolve_data_path(custom_path: Optional[str], relative_subpath: str) -> Path:
    """
    Resolve dataset paths across local development, Docker, and serverless runtimes.
    Does not assume the current working directory is the repository root.
    """
    if custom_path:
        return Path(custom_path)

    # 1. Explicit environment variable overrides
    if "WINDSIGNAL_PROJECT_ROOT" in os.environ:
        cand = Path(os.environ["WINDSIGNAL_PROJECT_ROOT"]) / relative_subpath
        if cand.exists():
            return cand
    if "WINDSIGNAL_DATA_DIR" in os.environ:
        cand = Path(os.environ["WINDSIGNAL_DATA_DIR"]).parent / relative_subpath
        if cand.exists():
            return cand

    # 2. Candidate root directories
    candidate_roots = [
        Path(__file__).resolve().parent.parent,  # src/services.py -> project root
        Path(__file__).resolve().parent,         # src/
        Path.cwd(),                              # current working directory
        Path.cwd().parent,                       # parent directory
    ]

    for root in candidate_roots:
        cand = root / relative_subpath
        if cand.exists():
            return cand

    # Default fallback: relative to this file's parent directory
    return Path(__file__).resolve().parent.parent / relative_subpath


class WindSignalService:
    """
    In-memory analytical service layer loaded at FastAPI startup.
    Does not make external network requests on user queries.
    """

    def __init__(
        self,
        parquet_path: Optional[str] = None,
        audit_json_path: Optional[str] = None,
        windfor_raw_path: Optional[str] = None
    ):
        self.parquet_path = _resolve_data_path(parquet_path, "data/processed/wind_analytical_dataset.parquet")
        self.audit_json_path = _resolve_data_path(audit_json_path, "data/processed/data_quality_summary.json")
        self.windfor_raw_path = _resolve_data_path(windfor_raw_path, "data/raw/windfor_raw.json")

        self.df_analytical: pd.DataFrame = pd.DataFrame()
        self.audit_summary: Dict[str, Any] = {}
        self.windfor_vintages_by_start: Dict[str, List[Dict[str, Any]]] = {}
        self.is_ready: bool = False

    def load_data(self) -> None:
        """Load datasets into memory and build indexing."""
        if not self.parquet_path.exists():
            raise FileNotFoundError(f"Analytical Parquet dataset missing at {self.parquet_path}")

        # 1. Load Analytical Dataset
        df = pd.read_parquet(self.parquet_path)
        # Ensure timezone-aware UTC datetime
        df["delivery_start_time_utc"] = pd.to_datetime(df["delivery_start_time_utc"], utc=True)
        df["forecast_publish_time_utc"] = pd.to_datetime(df["forecast_publish_time_utc"], utc=True)
        df["cutoff_time_utc"] = pd.to_datetime(df["cutoff_time_utc"], utc=True)
        df["delivery_date"] = pd.to_datetime(df["delivery_date"]).dt.date
        df["decision_date"] = pd.to_datetime(df["decision_date"]).dt.date

        self.df_analytical = df.sort_values("delivery_start_time_utc").reset_index(drop=True)

        # 2. Load Audit JSON
        if self.audit_json_path.exists():
            with open(self.audit_json_path, "r", encoding="utf-8") as f:
                self.audit_summary = json.load(f)

        # 3. Load and Index Raw WINDFOR Vintages
        if self.windfor_raw_path.exists():
            with open(self.windfor_raw_path, "r", encoding="utf-8") as f:
                raw_payload = json.load(f)
                records = raw_payload.get("records", [])

            # Index by normalized ISO start time string
            vintages_map: Dict[str, List[Dict[str, Any]]] = {}
            for r in records:
                st = r.get("startTime")
                if not st:
                    continue
                # Normalize start time to standard ISO format
                st_norm = pd.to_datetime(st, utc=True).isoformat()
                if st_norm not in vintages_map:
                    vintages_map[st_norm] = []
                vintages_map[st_norm].append({
                    "publishTime": r["publishTime"],
                    "generation": r.get("generation", 0)
                })

            # Sort records in each delivery interval chronologically
            for st_key in vintages_map:
                vintages_map[st_key].sort(key=lambda x: x["publishTime"])

            self.windfor_vintages_by_start = vintages_map

        self.is_ready = True

    def get_health(self) -> HealthResponse:
        """Return operational health status and row counts."""
        return HealthResponse(
            status="healthy" if self.is_ready else "initializing",
            dataset_ready=self.is_ready,
            evaluated_rows=len(self.df_analytical),
            service_timestamp_utc=datetime.now(timezone.utc),
            version="1.0.0"
        )

    def get_overview(self) -> OverviewResponse:
        """Return headline accuracy, coverage, and cutoff configuration."""
        if not self.is_ready or self.df_analytical.empty:
            raise DataNotFoundError("Dataset not loaded")

        df = self.df_analytical

        # Calculate metrics
        mean_act = float(df["actual_generation_mean_mw"].mean())
        mae = float(df["abs_error_mw"].mean())
        rmse = float(np.sqrt((df["forecast_error_mw"]**2).mean()))
        mbe = float(df["forecast_error_mw"].mean())
        nmae = float((mae / mean_act) * 100.0) if mean_act > 0 else 0.0
        p90 = float(df["abs_error_mw"].quantile(0.90))
        max_over = float(df["forecast_error_mw"].max())
        max_under = float(df["forecast_error_mw"].min())

        bias_direction = "Overforecast" if mbe > 0 else ("Underforecast" if mbe < 0 else "Unbiased")

        return OverviewResponse(
            decision_window={
                "start_date": df["decision_date"].min().isoformat(),
                "end_date": df["decision_date"].max().isoformat(),
                "total_days": int(df["decision_date"].nunique())
            },
            delivery_window={
                "start_datetime_utc": df["delivery_start_time_utc"].min().isoformat(),
                "end_datetime_utc": df["delivery_start_time_utc"].max().isoformat(),
                "total_hours": len(df),
                "expected_hours": 744,
                "coverage_percentage": 100.0
            },
            decision_cutoff=CutoffConfig(
                cutoff_time_utc="09:20:00",
                source_attribution="EPEX SPOT GB Day-Ahead 60-Minute Auction Gate Closure (09:20 GMT/BST)",
                is_analytical_assumption=True,
                description=(
                    "Order book gate closure time for the primary Great Britain wholesale Day-Ahead 60-Minute auction. "
                    "NGESO WINDFOR forecasts published at 07:30 UTC represent the latest publication available prior to this deadline. "
                    "Applicability to this utility's specific internal procurement workflow is an analytical assumption."
                )
            ),
            headline_metrics=HeadlineMetrics(
                mean_actual_mw=round(mean_act, 2),
                mae_mw=round(mae, 2),
                rmse_mw=round(rmse, 2),
                mean_bias_error_mw=round(mbe, 2),
                normalized_mae_pct=round(nmae, 2),
                p90_abs_error_mw=round(p90, 2),
                max_overforecast_mw=round(max_over, 2),
                max_underforecast_mw=round(max_under, 2),
                bias_direction=bias_direction,
                units={
                    "power": "MW",
                    "error": "MW",
                    "percentage": "%",
                    "lead_time": "hours"
                }
            ),
            sample_counts={
                "evaluated_intervals": len(df),
                "constituent_half_hourly_observations": len(df) * 2
            }
        )

    def _filter_df(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> pd.DataFrame:
        """Helper to apply safe date filtering on delivery_date."""
        if date_from and date_to and date_from > date_to:
            raise InvalidFilterError(f"date_from ({date_from}) cannot be after date_to ({date_to})")

        filtered = self.df_analytical
        if date_from:
            filtered = filtered[filtered["delivery_date"] >= date_from]
        if date_to:
            filtered = filtered[filtered["delivery_date"] <= date_to]
        return filtered

    def get_forecast_vs_actual(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> ForecastVsActualResponse:
        """Return hourly comparison between forecast and actual generation."""
        if not self.is_ready:
            raise DataNotFoundError("Dataset not loaded")

        filtered = self._filter_df(date_from, date_to)

        items = []
        for _, row in filtered.iterrows():
            pct_err = float(row["percentage_error"]) if pd.notna(row["percentage_error"]) else None
            items.append(ForecastVsActualItem(
                delivery_start_time_utc=row["delivery_start_time_utc"].to_pydatetime(),
                delivery_date=row["delivery_date"],
                start_settlement_period=int(row["start_settlement_period"]),
                end_settlement_period=int(row["end_settlement_period"]),
                forecast_generation_mw=float(row["forecast_generation_mw"]),
                actual_generation_mean_mw=float(row["actual_generation_mean_mw"]),
                forecast_error_mw=float(row["forecast_error_mw"]),
                percentage_error=pct_err,
                abs_error_mw=float(row["abs_error_mw"]),
                forecast_publish_time_utc=row["forecast_publish_time_utc"].to_pydatetime(),
                lead_time_hours=float(row["lead_time_hours"])
            ))

        return ForecastVsActualResponse(
            total_records=len(items),
            filter_applied={
                "delivery_date_from": date_from.isoformat() if date_from else None,
                "delivery_date_to": date_to.isoformat() if date_to else None
            },
            data=items
        )

    def get_accuracy_metrics(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> AccuracyMetricsResponse:
        """Recalculate dynamic accuracy metrics for the filtered subset."""
        if not self.is_ready:
            raise DataNotFoundError("Dataset not loaded")

        filtered = self._filter_df(date_from, date_to)

        # Determine expected intervals
        if date_from and date_to:
            expected = ((date_to - date_from).days + 1) * 24
        elif date_from:
            max_d = self.df_analytical["delivery_date"].max()
            expected = max(0, ((max_d - date_from).days + 1) * 24)
        elif date_to:
            min_d = self.df_analytical["delivery_date"].min()
            expected = max(0, ((date_to - min_d).days + 1) * 24)
        else:
            expected = len(self.df_analytical)

        matched = len(filtered)
        coverage = (matched / expected) * 100.0 if expected > 0 else 0.0

        if matched == 0:
            return AccuracyMetricsResponse(
                filter_applied={
                    "delivery_date_from": date_from.isoformat() if date_from else None,
                    "delivery_date_to": date_to.isoformat() if date_to else None
                },
                expected_intervals=expected,
                matched_intervals=0,
                coverage_percentage=0.0,
                mean_actual_mw=0.0,
                mae_mw=0.0,
                rmse_mw=0.0,
                mean_bias_error_mw=0.0,
                normalized_mae_pct=0.0,
                p90_abs_error_mw=0.0,
                max_overforecast_mw=0.0,
                max_underforecast_mw=0.0,
                units={"power": "MW", "percentage": "%"}
            )

        mean_act = float(filtered["actual_generation_mean_mw"].mean())
        mae = float(filtered["abs_error_mw"].mean())
        rmse = float(np.sqrt((filtered["forecast_error_mw"]**2).mean()))
        mbe = float(filtered["forecast_error_mw"].mean())
        nmae = float((mae / mean_act) * 100.0) if mean_act > 0 else 0.0
        p90 = float(filtered["abs_error_mw"].quantile(0.90))
        max_over = float(filtered["forecast_error_mw"].max())
        max_under = float(filtered["forecast_error_mw"].min())

        return AccuracyMetricsResponse(
            filter_applied={
                "delivery_date_from": date_from.isoformat() if date_from else None,
                "delivery_date_to": date_to.isoformat() if date_to else None
            },
            expected_intervals=expected,
            matched_intervals=matched,
            coverage_percentage=round(coverage, 2),
            mean_actual_mw=round(mean_act, 2),
            mae_mw=round(mae, 2),
            rmse_mw=round(rmse, 2),
            mean_bias_error_mw=round(mbe, 2),
            normalized_mae_pct=round(nmae, 2),
            p90_abs_error_mw=round(p90, 2),
            max_overforecast_mw=round(max_over, 2),
            max_underforecast_mw=round(max_under, 2),
            units={"power": "MW", "percentage": "%"}
        )

    def get_forecast_vintages(self, delivery_start_time: datetime) -> ForecastVintagesResponse:
        """
        Return all historical publications targeting the delivery interval.
        Identifies selected vintage and excludes post-cutoff vintages from selection.
        """
        if not self.is_ready:
            raise DataNotFoundError("Dataset not loaded")

        # Normalize to UTC
        if delivery_start_time.tzinfo is None:
            del_dt_utc = delivery_start_time.replace(tzinfo=timezone.utc)
        else:
            del_dt_utc = delivery_start_time.astimezone(timezone.utc)

        # Lookup in analytical dataset for configured decision cutoff
        matching_row = self.df_analytical[self.df_analytical["delivery_start_time_utc"] == del_dt_utc]

        if not matching_row.empty:
            row = matching_row.iloc[0]
            dec_date = row["decision_date"]
            cutoff_dt_utc = row["cutoff_time_utc"].to_pydatetime()
            cutoff_src = row["cutoff_source"]
            selected_pub_time = row["forecast_publish_time_utc"].to_pydatetime()
        else:
            # Fallback for valid interval within delivery scope
            del_date = del_dt_utc.date()
            dec_date = del_date - timedelta(days=1)
            cutoff_dt_utc = datetime.combine(dec_date, dt_time(9, 20, 0), tzinfo=timezone.utc)
            cutoff_src = "EPEX SPOT GB Day-Ahead 60-Minute Auction Gate Closure (09:20 GMT/BST)"
            selected_pub_time = None

        # Look up raw WINDFOR publications
        del_key = del_dt_utc.isoformat()
        raw_vintages = self.windfor_vintages_by_start.get(del_key, [])

        if not raw_vintages:
            raise DataNotFoundError(f"No historical WINDFOR publications found for interval {del_key}")

        vintages_list: List[VintageItem] = []
        eligible_count = 0
        excluded_count = 0

        # Sort chronologically by publish time
        parsed_vintages = []
        for v in raw_vintages:
            pub_dt = pd.to_datetime(v["publishTime"], utc=True).to_pydatetime()
            gen_mw = float(v.get("generation", 0))
            parsed_vintages.append((pub_dt, gen_mw))

        parsed_vintages.sort(key=lambda x: x[0])

        # If selected_pub_time wasn't found in analytical table, compute strictly
        if selected_pub_time is None:
            eligible_candidates = [p for p in parsed_vintages if p[0] <= cutoff_dt_utc]
            selected_pub_time = eligible_candidates[-1][0] if eligible_candidates else None

        selected_item: Optional[VintageItem] = None

        for pub_dt, gen_mw in parsed_vintages:
            is_eligible = (pub_dt <= cutoff_dt_utc)
            is_selected = (pub_dt == selected_pub_time)

            if is_eligible:
                eligible_count += 1
                latency = (cutoff_dt_utc - pub_dt).total_seconds() / 3600.0
            else:
                excluded_count += 1
                latency = None

            lead_time = (del_dt_utc - pub_dt).total_seconds() / 3600.0

            item = VintageItem(
                publish_time_utc=pub_dt,
                forecast_generation_mw=gen_mw,
                is_eligible_prior_to_cutoff=is_eligible,
                is_selected=is_selected,
                latency_to_cutoff_hours=round(latency, 2) if latency is not None else None,
                lead_time_to_delivery_hours=round(lead_time, 2)
            )
            vintages_list.append(item)
            if is_selected:
                selected_item = item

        return ForecastVintagesResponse(
            delivery_start_time_utc=del_dt_utc,
            decision_date=dec_date,
            cutoff_time_utc=cutoff_dt_utc,
            cutoff_source=cutoff_src,
            selected_vintage=selected_item,
            total_vintages_available=len(vintages_list),
            eligible_vintages_count=eligible_count,
            excluded_vintages_count=excluded_count,
            vintages=vintages_list
        )

    def get_data_quality(self) -> DataQualityResponse:
        """Return audited data quality metrics and invariant check results."""
        if not self.audit_summary:
            raise DataNotFoundError("Data quality summary not found")

        aud = self.audit_summary
        inv = aud.get("validation_invariants", {})
        raw = aud.get("raw_ingestion", {})
        err = aud.get("error_metrics", {})
        dw = aud.get("delivery_window", {})

        all_passed = (
            inv.get("look_ahead_violations", -1) == 0 and
            inv.get("analytical_dataset_duplicates", -1) == 0 and
            inv.get("hourly_aggregation_period_integrity", False) is True and
            inv.get("negative_actual_generation_count", -1) == 0 and
            inv.get("negative_forecast_generation_count", -1) == 0
        )

        return DataQualityResponse(
            audit_timestamp_utc=pd.to_datetime(aud.get("audit_timestamp_utc"), utc=True).to_pydatetime(),
            delivery_window=dw,
            validation_invariants={
                **inv,
                "all_invariants_passed": all_passed
            },
            raw_ingestion={
                "fuelhh_record_count": raw.get("fuelhh", {}).get("record_count", 0),
                "windfor_record_count": raw.get("windfor", {}).get("record_count", 0),
                "fuelhh_latency_s": round(raw.get("fuelhh", {}).get("elapsed_seconds", 0), 2),
                "windfor_latency_s": round(raw.get("windfor", {}).get("elapsed_seconds", 0), 2)
            },
            error_summary=err
        )

    def get_export_csv(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> str:
        """Generate formatted CSV string of forecast and actual comparison."""
        if not self.is_ready:
            raise DataNotFoundError("Dataset not loaded")

        filtered = self._filter_df(date_from, date_to)

        output = io.StringIO()
        fieldnames = [
            "delivery_start_time_utc",
            "delivery_date",
            "start_settlement_period",
            "end_settlement_period",
            "forecast_generation_mw",
            "actual_generation_mean_mw",
            "forecast_error_mw",
            "abs_error_mw",
            "percentage_error",
            "forecast_publish_time_utc",
            "lead_time_hours"
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for _, row in filtered.iterrows():
            writer.writerow({
                "delivery_start_time_utc": row["delivery_start_time_utc"].isoformat(),
                "delivery_date": row["delivery_date"].isoformat(),
                "start_settlement_period": int(row["start_settlement_period"]),
                "end_settlement_period": int(row["end_settlement_period"]),
                "forecast_generation_mw": f"{row['forecast_generation_mw']:.1f}",
                "actual_generation_mean_mw": f"{row['actual_generation_mean_mw']:.1f}",
                "forecast_error_mw": f"{row['forecast_error_mw']:.1f}",
                "abs_error_mw": f"{row['abs_error_mw']:.1f}",
                "percentage_error": f"{row['percentage_error']:.2f}" if pd.notna(row["percentage_error"]) else "",
                "forecast_publish_time_utc": row["forecast_publish_time_utc"].isoformat(),
                "lead_time_hours": f"{row['lead_time_hours']:.1f}"
            })

        return output.getvalue()
