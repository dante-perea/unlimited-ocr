"""Integration tests for the combined NCBI + OCR app (offline-safe paths).

These exercise the FastAPI app as wired in ``app.main`` — i.e. that the NCBI and
OCR routers are both mounted and that their input-validation / not-found paths
behave as the frontend expects. They deliberately avoid the network paths (real
NCBI search / PDF download) so the suite is fast and deterministic; the live
end-to-end flow is verified separately against a running backend.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_ok() -> None:
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "device" in body


def test_routes_mounted() -> None:
    paths = {getattr(route, "path", "") for route in app.routes}
    for expected in (
        "/health",
        "/ncbi/search",
        "/ncbi/paper/{pmcid}",
        "/ncbi/fetch/{pmcid}",
        "/ocr/run",
        "/ocr/status/{job_id}",
    ):
        assert expected in paths, f"missing route {expected}"


def test_search_requires_query() -> None:
    with TestClient(app) as client:
        r = client.get("/ncbi/search", params={"query": "   "})
    assert r.status_code == 400


def test_fetch_rejects_bad_pmcid() -> None:
    with TestClient(app) as client:
        r = client.post("/ncbi/fetch/not-a-pmc-id")
    assert r.status_code == 400


def test_ocr_run_requires_input() -> None:
    with TestClient(app) as client:
        r = client.post("/ocr/run", json={})
    assert r.status_code == 422


def test_ocr_status_unknown_job_is_404() -> None:
    with TestClient(app) as client:
        r = client.get("/ocr/status/does-not-exist")
    assert r.status_code == 404
