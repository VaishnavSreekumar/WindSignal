"""
WindSignal Deployment & Configuration Invariant Test Suite
===========================================================
Validates:
1. Root pyproject.toml configuration and custom Vercel entrypoint.
2. Root vercel.json serverless function packaging and rewrites.
3. Frontend vercel.json SPA routing integrity.
4. Dataset path resolution independence from working directory.
5. All seven API endpoint paths retention and HTTP 200 status.
6. CORS configuration with Vercel preview domain support.
"""

import json
import os
import tomllib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.services import WindSignalService, _resolve_data_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_root_pyproject_toml_vercel_entrypoint():
    """Verify root pyproject.toml exists and declares tool.vercel.entrypoint = src.api:app."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml must exist at repository root"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    assert "tool" in data, "pyproject.toml must contain [tool] table"
    assert "vercel" in data["tool"], "pyproject.toml must contain [tool.vercel] table"
    assert data["tool"]["vercel"].get("entrypoint") == "src.api:app", (
        "tool.vercel.entrypoint must point to 'src.api:app'"
    )


def test_root_vercel_json_functions_and_rewrites():
    """Verify root vercel.json configures src/api.py with data inclusion and rewrite."""
    vercel_path = PROJECT_ROOT / "vercel.json"
    assert vercel_path.exists(), "vercel.json must exist at repository root"

    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "functions" in data, "vercel.json must configure 'functions'"
    assert "src/api.py" in data["functions"], "functions must include 'src/api.py'"
    func_cfg = data["functions"]["src/api.py"]
    assert "data/**" in func_cfg.get("includeFiles", ""), "includeFiles must bundle 'data/**'"

    assert "rewrites" in data, "vercel.json must configure 'rewrites'"
    rewrite_destinations = [r.get("destination") for r in data["rewrites"]]
    assert "/src/api.py" in rewrite_destinations, "rewrites must target /src/api.py"


def test_frontend_vercel_json_spa_rewrite():
    """Verify frontend/vercel.json is preserved with SPA routing rewrite."""
    fe_vercel_path = PROJECT_ROOT / "frontend" / "vercel.json"
    assert fe_vercel_path.exists(), "frontend/vercel.json must exist"

    with open(fe_vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "rewrites" in data, "frontend/vercel.json must contain rewrites"
    assert data["rewrites"][0]["destination"] == "/index.html"


def test_dataset_resolution_independent_of_cwd(tmp_path):
    """
    Verify WindSignalService and _resolve_data_path locate datasets
    even when the current working directory is an unrelated temporary directory.
    """
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Verify resolution without cwd reliance
        parquet_resolved = _resolve_data_path(None, "data/processed/wind_analytical_dataset.parquet")
        assert parquet_resolved.exists(), f"Failed to locate parquet from cwd {tmp_path}"

        audit_resolved = _resolve_data_path(None, "data/processed/data_quality_summary.json")
        assert audit_resolved.exists(), f"Failed to locate audit json from cwd {tmp_path}"

        service = WindSignalService()
        service.load_data()
        assert service.is_ready is True
        assert len(service.df_analytical) == 744
    finally:
        os.chdir(orig_cwd)


def test_all_seven_endpoints_retained_and_healthy():
    """
    Verify all 7 documented endpoints retain exact paths and return 200 OK.
    """
    endpoints = [
        ("GET", "/api/health"),
        ("GET", "/api/overview"),
        ("GET", "/api/forecast-vs-actual"),
        ("GET", "/api/accuracy"),
        ("GET", "/api/forecast-vintages?delivery_start_time=2026-01-15T12:00:00Z"),
        ("GET", "/api/data-quality"),
        ("GET", "/api/export.csv"),
    ]

    with TestClient(app) as client:
        # Also test root descriptor endpoint
        root_resp = client.get("/")
        assert root_resp.status_code == 200
        assert root_resp.json()["service"] == "WindSignal API"

        for method, path in endpoints:
            resp = client.request(method, path)
            assert resp.status_code == 200, f"Endpoint {path} failed: {resp.status_code}"


def test_cors_vercel_preview_origin_allowed(monkeypatch):
    """Verify that requests from vercel.app domains are accepted by CORS."""
    with TestClient(app) as client:
        # Preflight OPTIONS request with Vercel preview origin
        headers = {
            "Origin": "https://windsignal-preview-git-branch.vercel.app",
            "Access-Control-Request-Method": "GET"
        }
        resp = client.options("/api/health", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://windsignal-preview-git-branch.vercel.app"
