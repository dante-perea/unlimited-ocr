"""Tests for the OCR endpoint contract (POST /ocr/run, GET /ocr/status/{id}).

The real model is never loaded: OCR_MOCK=1 yields canned output, and we also
test that a CUDA-requirement failure surfaces as a clear 422.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app
from app.services import ocr_model


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """App client with a mock model (OCR_MOCK=1) forced on."""
    monkeypatch.setenv("OCR_MOCK", "1")
    app = create_app()
    with TestClient(app) as c:
        yield c


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 10.0) -> dict:
    """Poll status until terminal, return the JSON body."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/ocr/status/{job_id}").json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def test_health_reports_device(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert "device" in body


def test_run_requires_pmcid_or_pdf_path(client: TestClient) -> None:
    res = client.post("/ocr/run", json={})
    assert res.status_code == 422


def test_run_returns_202_and_job_id(client: TestClient, sample_pdf: Path) -> None:
    res = client.post("/ocr/run", json={"pdf_path": str(sample_pdf)})
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "queued"
    assert body["job_id"]
    assert body["poll"] == f"/ocr/status/{body['job_id']}"


def test_status_unknown_job_is_404(client: TestClient) -> None:
    res = client.get("/ocr/status/does-not-exist")
    assert res.status_code == 404


def test_full_mock_run_returns_pages_full_text_and_facts(
    client: TestClient, sample_pdf: Path
) -> None:
    res = client.post("/ocr/run", json={"pdf_path": str(sample_pdf)})
    assert res.status_code == 202
    body = _wait_for_job(client, res.json()["job_id"])

    assert body["status"] == "completed"
    result = body["result"]
    # Contract: { pages, full_text, facts }.
    assert set(result) >= {"pages", "full_text", "facts"}
    assert isinstance(result["pages"], list)
    assert result["n_pages"] == len(result["pages"])
    assert result["full_text"]  # non-empty
    assert result["mock"] is True
    assert result["device"] == "mock"
    facts = result["facts"]
    assert facts["extractor"] == "heuristic"
    # Canned content has a title, authors, a finding and a DOI/PMCID.
    assert facts["title"]
    assert facts["authors"]
    assert facts["doi"]
    assert facts["pmcid"]


def test_multipage_mock_run(client: TestClient, multipage_pdf: Path) -> None:
    res = client.post("/ocr/run", json={"pdf_path": str(multipage_pdf)})
    assert res.status_code == 202
    body = _wait_for_job(client, res.json()["job_id"])
    assert body["status"] == "completed"
    assert body["result"]["n_pages"] == 3
# --------------------------------------------------------------------------- #
# pmcid resolution against the NCBI PDF cache.
# --------------------------------------------------------------------------- #

def test_run_with_pmcid_resolves_cached_pdf(
    monkeypatch: pytest.MonkeyPatch, sample_pdf: Path, tmp_path: Path
) -> None:
    """Stage a cached PDF, point PDF_CACHE_DIR at it, and run via pmcid."""
    cache_dir = tmp_path / "pdfs"
    cache_dir.mkdir()
    (cache_dir / "PMC9999999.pdf").write_bytes(sample_pdf.read_bytes())

    monkeypatch.setenv("OCR_MOCK", "1")
    monkeypatch.setenv("PDF_CACHE_DIR", str(cache_dir))

    app = create_app()
    with TestClient(app) as client:
        res = client.post("/ocr/run", json={"pmcid": "PMC9999999"})
        assert res.status_code == 202, res.text
        body = _wait_for_job(client, res.json()["job_id"])
        assert body["status"] == "completed"
        assert body["result"]["facts"]["pmcid"] == "PMC9999999"


# --------------------------------------------------------------------------- #
# CUDA-requirement failure surfaces as a clear 422.
# --------------------------------------------------------------------------- #

class _CudaFailingModel:
    """Model whose infer raises a CUDA-looking RuntimeError (simulates MPS/CPU)."""

    def infer(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("LayerNorm not implemented for 'BFloat16' on MPS device.")

    def infer_multi(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("Expected all tensors to be on cuda but found cpu")


def test_gpu_requirement_failure_returns_422(
    client: TestClient, sample_pdf: Path
) -> None:
    # Force a non-mock singleton whose model fails at infer time.
    ocr_model.reset_model()
    ocr_model._model_singleton = (_CudaFailingModel(), None, "mps")  # type: ignore[attr-defined]
    try:
        res = client.post("/ocr/run", json={"pdf_path": str(sample_pdf)})
        assert res.status_code == 202
        job_id = res.json()["job_id"]

        # Poll: a gpu_required failure makes the status endpoint return 422 with an
        # actionable body (rather than a 200 status snapshot).
        deadline = time.time() + 10.0
        while time.time() < deadline:
            status_res = client.get(f"/ocr/status/{job_id}")
            if status_res.status_code == 422:
                detail = status_res.json()["detail"]
                assert detail["error_code"] == "gpu_required"
                assert "CUDA" in detail["message"]
                return
            if status_res.status_code == 200 and status_res.json()["status"] == "failed":
                break  # failed but not gpu_required — fall through to the assert below
            time.sleep(0.05)
        raise AssertionError("expected a 422 gpu_required response")
    finally:
        ocr_model.reset_model()


def test_model_singleton_loaded_once(client: TestClient, sample_pdf: Path) -> None:
    """get_model must return the cached singleton across calls (load once)."""
    from app.config import get_settings

    ocr_model.reset_model()
    settings = get_settings()
    bundle1 = ocr_model.get_model(settings)
    bundle2 = ocr_model.get_model(settings)
    assert bundle1 is bundle2
    # ModelBundle is a type alias (tuple[Any, Any, str]); check shape + device.
    assert isinstance(bundle1, tuple) and len(bundle1) == 3
    assert bundle1[2] == "mock"  # OCR_MOCK=1 in the suite
