"""
WindSignal FastAPI Application
==============================
Production-minded REST API serving validated UK wind forecast accuracy analytics.
"""

import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Query, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.schemas import (
    HealthResponse,
    OverviewResponse,
    ForecastVsActualResponse,
    AccuracyMetricsResponse,
    ForecastVintagesResponse,
    DataQualityResponse,
)
from src.services import (
    WindSignalService,
    DataNotFoundError,
    InvalidFilterError,
)

# Global service instance
service = WindSignalService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to load datasets into memory at application startup."""
    try:
        service.load_data()
    except Exception as exc:
        # Service starts in unready state if data loading fails
        print(f"[ERROR] Failed to load WindSignal dataset at startup: {exc}")
    yield


app = FastAPI(
    title="WindSignal API",
    description="UK Day-Ahead Wind Generation Forecast Accuracy Analytics Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# -------------------------------------------------------------------------
# CORS Configuration
# -------------------------------------------------------------------------
cors_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
allow_all = "*" in origins

# Allow Vercel preview and production deployments (.vercel.app) by default
allow_vercel_regex = os.getenv("CORS_ORIGIN_REGEX", r"^https:\/\/.*\.vercel\.app$")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else origins,
    allow_origin_regex=None if allow_all else allow_vercel_regex,
    allow_credentials=not allow_all,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get(
    "/",
    tags=["System"],
    summary="API Root and Documentation Index",
    include_in_schema=False
)
def get_root():
    """Root endpoint providing service identity and navigation links."""
    return {
        "service": "WindSignal API",
        "description": "UK Day-Ahead Wind Generation Forecast Accuracy Analytics Platform",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/api/health",
        "overview_url": "/api/overview"
    }


# -------------------------------------------------------------------------
# Exception Handlers
# -------------------------------------------------------------------------
@app.exception_handler(DataNotFoundError)
async def handle_data_not_found(request: Request, exc: DataNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)}
    )


@app.exception_handler(InvalidFilterError)
async def handle_invalid_filter(request: Request, exc: InvalidFilterError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception):
    # Public error message without internal stack trace or filesystem paths
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred processing the analytics request."}
    )


# -------------------------------------------------------------------------
# REST API Endpoints
# -------------------------------------------------------------------------

@app.get(
    "/api/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health and Dataset Readiness Check"
)
def get_health() -> HealthResponse:
    """Return operational service health, dataset readiness, and evaluated row count."""
    return service.get_health()


@app.get(
    "/api/overview",
    response_model=OverviewResponse,
    tags=["Analytics"],
    summary="Executive Overview and Headline Metrics"
)
def get_overview() -> OverviewResponse:
    """
    Return full-window headline accuracy metrics, coverage, and documented
    decision cutoff details.
    """
    return service.get_overview()


@app.get(
    "/api/forecast-vs-actual",
    response_model=ForecastVsActualResponse,
    tags=["Analytics"],
    summary="Hourly Forecast vs. Actual Time-Series"
)
def get_forecast_vs_actual(
    delivery_date_from: Optional[date] = Query(
        None,
        description="Filter delivery dates from (YYYY-MM-DD), inclusive"
    ),
    delivery_date_to: Optional[date] = Query(
        None,
        description="Filter delivery dates to (YYYY-MM-DD), inclusive"
    )
) -> ForecastVsActualResponse:
    """
    Return hourly delivery interval observations including forecast MW,
    actual MW, signed error, and lead time. Supports optional date window filtering.
    """
    return service.get_forecast_vs_actual(
        date_from=delivery_date_from,
        date_to=delivery_date_to
    )


@app.get(
    "/api/accuracy",
    response_model=AccuracyMetricsResponse,
    tags=["Analytics"],
    summary="Dynamic Accuracy & Error Metrics"
)
def get_accuracy(
    delivery_date_from: Optional[date] = Query(
        None,
        description="Filter delivery dates from (YYYY-MM-DD), inclusive"
    ),
    delivery_date_to: Optional[date] = Query(
        None,
        description="Filter delivery dates to (YYYY-MM-DD), inclusive"
    )
) -> AccuracyMetricsResponse:
    """
    Return dynamically recalculated accuracy metrics (MAE, RMSE, MBE, NMAE, P90 error)
    for the specified delivery date range.
    """
    return service.get_accuracy_metrics(
        date_from=delivery_date_from,
        date_to=delivery_date_to
    )


@app.get(
    "/api/forecast-vintages",
    response_model=ForecastVintagesResponse,
    tags=["Analytics"],
    summary="Historical Forecast Vintages for Delivery Interval"
)
def get_forecast_vintages(
    delivery_start_time: str = Query(
        ...,
        description="Target delivery interval in ISO 8601 UTC format (e.g. 2026-01-02T12:00:00Z)"
    )
) -> ForecastVintagesResponse:
    """
    Return all historical publication runs targeting a specific delivery hour.
    Distinguishes pre-cutoff eligible forecasts from post-cutoff excluded runs,
    identifying the exact vintage selected for day-ahead procurement.
    """
    try:
        parsed_dt = datetime.fromisoformat(delivery_start_time.replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid timestamp format '{delivery_start_time}'. Use ISO 8601 UTC (e.g. 2026-01-02T12:00:00Z)."
        )

    return service.get_forecast_vintages(delivery_start_time=parsed_dt)


@app.get(
    "/api/data-quality",
    response_model=DataQualityResponse,
    tags=["Quality & Audit"],
    summary="Data Quality Audit & Invariant Checks"
)
def get_data_quality() -> DataQualityResponse:
    """
    Return comprehensive data quality audit results, boundary counts,
    and validation invariant checks.
    """
    return service.get_data_quality()


@app.get(
    "/api/export.csv",
    tags=["Export"],
    summary="Export Forecast vs Actual Data as CSV"
)
def export_csv(
    delivery_date_from: Optional[date] = Query(
        None,
        description="Filter delivery dates from (YYYY-MM-DD), inclusive"
    ),
    delivery_date_to: Optional[date] = Query(
        None,
        description="Filter delivery dates to (YYYY-MM-DD), inclusive"
    )
) -> Response:
    """
    Download a formatted CSV export of the hourly forecast versus actual comparison
    dataset with optional date range filtering.
    """
    csv_content = service.get_export_csv(
        date_from=delivery_date_from,
        date_to=delivery_date_to
    )
    filename = "windsignal_forecast_vs_actual.csv"
    if delivery_date_from and delivery_date_to:
        filename = f"windsignal_forecast_vs_actual_{delivery_date_from}_{delivery_date_to}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
