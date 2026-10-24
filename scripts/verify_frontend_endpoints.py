import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from src.api import app

def verify_all_endpoints():
    with TestClient(app) as client:
        endpoints = [
            ("GET", "/api/health", {}),
            ("GET", "/api/overview", {}),
            ("GET", "/api/forecast-vs-actual", {}),
            ("GET", "/api/forecast-vs-actual?delivery_date_from=2026-01-05&delivery_date_to=2026-01-10", {}),
            ("GET", "/api/accuracy", {}),
            ("GET", "/api/accuracy?delivery_date_from=2026-01-05&delivery_date_to=2026-01-10", {}),
            ("GET", "/api/forecast-vintages?delivery_start_time=2026-01-15T12:00:00Z", {}),
            ("GET", "/api/data-quality", {}),
            ("GET", "/api/export.csv", {}),
        ]

        print("Verifying frontend endpoint contracts against FastAPI...")
        for method, path, kwargs in endpoints:
            resp = client.request(method, path, **kwargs)
            assert resp.status_code == 200, f"Endpoint {path} failed with {resp.status_code}: {resp.text}"
            if path.endswith(".csv"):
                assert "text/csv" in resp.headers["content-type"]
                assert "delivery_start_time_utc" in resp.text
                print(f"[OK] {method} {path} -> 200 OK (Content-Type: text/csv, {len(resp.text)} chars)")
            else:
                assert resp.headers["content-type"] == "application/json"
                data = resp.json()
                print(f"[OK] {method} {path} -> 200 OK (Keys: {list(data.keys())[:5]})")

        # Verify exact P90 metric contract consistency across Overview and Accuracy
        ov_data = client.get("/api/overview").json()
        acc_data = client.get("/api/accuracy").json()
        ov_p90 = ov_data["headline_metrics"]["p90_abs_error_mw"]
        acc_p90 = acc_data["p90_abs_error_mw"]
        assert ov_p90 == acc_p90 == 4097.90, f"P90 mismatch: overview={ov_p90}, accuracy={acc_p90}"
        print(f"[OK] Verified P90 Consistency: {ov_p90} MW across /api/overview and /api/accuracy")
                
        print("\nALL FRONTEND ENDPOINT CALLS VERIFIED AGAINST REAL BACKEND!")

if __name__ == "__main__":
    verify_all_endpoints()
