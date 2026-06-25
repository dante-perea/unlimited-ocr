"""Shared pytest fixtures for the backend.

Covers two areas:

* **NCBI integration** — upstream NCBI/PMC calls are mocked with
  :class:`httpx.MockTransport`, injected directly into the
  :class:`NcbiService` (the service accepts a custom ``client``). The FastAPI
  ``get_ncbi_service`` dependency is overridden so the router uses the mocked
  service. These tests run fully offline.

* **OCR pipeline** — the whole suite runs in mock/offline mode
  (``OCR_MOCK=1``) so it never needs torch, transformers, or model weights.
  Endpoint tests additionally reset the in-memory settings cache per-test so
  ``model_copy`` overrides / env flags don't leak between tests.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

# Force mock/offline mode for the entire suite before any app import.
os.environ["OCR_MOCK"] = "1"

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.services.ncbi import NcbiService, RateLimiter, get_ncbi_service
from app.services import ocr_model

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_json(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text())


def load_text(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


# --------------------------------------------------------------------------- #
# Per-test cache resets (OCR pipeline)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _reset_caches():
    """Reset the settings cache + model singleton before each test."""
    get_settings.cache_clear()
    ocr_model.reset_model()
    yield
    get_settings.cache_clear()
    ocr_model.reset_model()


# --------------------------------------------------------------------------- #
# Configurable NCBI mock
# --------------------------------------------------------------------------- #


class NcbiMock:
    """A callable that answers :class:`httpx.Request` objects like NCBI would."""

    def __init__(self) -> None:
        self.esearch: Any = load_json("esearch_two.json")
        self.esummary: Any = load_json("esummary_two.json")
        self.efetch: str = load_text("efetch_abstracts.xml")
        self.oa_by_id: dict[str, str] = {}
        self.downloads: dict[str, bytes] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/esearch.fcgi"):
            return httpx.Response(200, json=self.esearch)
        if request.url.path.endswith("/esummary.fcgi"):
            return httpx.Response(200, json=self.esummary)
        if request.url.path.endswith("/efetch.fcgi"):
            return httpx.Response(
                200, text=self.efetch, headers={"content-type": "application/xml"}
            )
        if request.url.path.endswith("/oa.fcgi"):
            pmcid = request.url.params.get("id", "")
            body = self.oa_by_id.get(pmcid)
            if body is None:
                return httpx.Response(
                    200,
                    text=(
                        "<OA><error>Cannot get document for id="
                        f"{pmcid}</error></OA>"
                    ),
                    headers={"content-type": "application/xml"},
                )
            return httpx.Response(
                200, text=body, headers={"content-type": "application/xml"}
            )
        # Binary downloads (PDF or tgz) resolved from OA links.
        for prefix, content in self.downloads.items():
            if prefix in str(request.url):
                return httpx.Response(200, content=content)
        return httpx.Response(404, text=f"unmocked request: {request.url}")


# --------------------------------------------------------------------------- #
# NCBI fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    d = tmp_path / "pdfs"
    d.mkdir()
    return d


@pytest.fixture
def install_service(cache_dir: Path):
    """Factory: build a mocked :class:`NcbiService` and install it on the app.

    Pass ``api_key=...`` to configure an NCBI API key on the service's settings.
    """

    def _install(
        handler: Callable[[httpx.Request], httpx.Response],
        *,
        api_key: str = "",
    ) -> NcbiService:
        settings = Settings(pdf_cache_dir=str(cache_dir), ncbi_api_key=api_key)
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        svc = NcbiService(settings, client=client)
        # Avoid real rate-limit delays during tests.
        svc._limiter = RateLimiter(rate_per_second=1_000_000)
        app.dependency_overrides[get_ncbi_service] = lambda: svc
        return svc

    yield _install
    app.dependency_overrides.pop(get_ncbi_service, None)


@pytest.fixture
def client(install_service, monkeypatch, tmp_path):
    """A ``TestClient`` whose CWD is a temp dir (isolates the default data dir)."""
    monkeypatch.chdir(tmp_path)
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- #
# Synthetic PDF fixtures (OCR pipeline) — built with PyMuPDF (no network/disk).
# --------------------------------------------------------------------------- #

def _make_pdf(path: Path, pages: list[str]) -> Path:
    import fitz  # PyMuPDF

    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """A 2-page PDF with a heading + author byline on page 1."""
    return _make_pdf(
        tmp_path / "sample.pdf",
        [
            "Title: A Sample Paper\nAlice B. Author, Bob C. Writer",
            "## Abstract\nWe show that the test passes. Our results confirm it.",
        ],
    )


@pytest.fixture()
def multipage_pdf(tmp_path: Path) -> Path:
    """A 3-page PDF used to exercise the multi-page (infer_multi) path."""
    return _make_pdf(
        tmp_path / "multi.pdf",
        ["Page one content", "Page two content", "Page three content"],
    )
