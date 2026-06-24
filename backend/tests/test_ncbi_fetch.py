"""Integration tests for POST /ncbi/fetch/{pmcid} and the cache convention.

The cached PDF lands at ``<pdf_cache_dir>/PMC<id>.pdf`` — the path the OCR
pipeline (``app.routers.ocr`` / ``OcrRunRequest.pmcid``) reads by PMCID.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import httpx

from tests.conftest import NcbiMock, load_json, load_text

FAKE_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _make_tgz(name: str = "paper.pdf", content: bytes = FAKE_PDF) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def test_fetch_downloads_pdf(install_service, client, cache_dir):
    """A direct PDF link is downloaded into the pdf cache directory."""
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text("oa_pdf.xml")}
    mock.downloads = {"WJR-9-27.PMC5334499.pdf": FAKE_PDF}
    install_service(mock)

    resp = client.post("/ncbi/fetch/PMC5334499")
    assert resp.status_code == 200
    body = resp.json()

    assert body["pmcid"] == "PMC5334499"
    assert body["status"] == "downloaded"
    assert body["source_format"] == "pdf"
    assert body["size_bytes"] == len(FAKE_PDF)
    assert body["filename"] == "PMC5334499.pdf"

    pdf_path = Path(body["pdf_path"])
    # Cached at the OCR-consumable convention: <pdf_cache_dir>/PMC<id>.pdf
    assert pdf_path == cache_dir / "PMC5334499.pdf"
    assert pdf_path.read_bytes() == FAKE_PDF


def test_fetch_reuses_cache(install_service, client):
    """A second call returns 'cached' without re-downloading."""
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text("oa_pdf.xml")}
    mock.downloads = {"WJR-9-27.PMC5334499.pdf": FAKE_PDF}
    install_service(mock)

    first = client.post("/ncbi/fetch/PMC5334499").json()
    assert first["status"] == "downloaded"

    second = client.post("/ncbi/fetch/PMC5334499").json()
    assert second["status"] == "cached"
    assert second["pdf_path"] == first["pdf_path"]


def test_fetch_extracts_pdf_from_tgz(install_service, client, cache_dir):
    """When only a .tar.gz package exists, the embedded PDF is extracted."""
    tgz_bytes = _make_tgz(name="subdir/paper.pdf", content=FAKE_PDF)
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text("oa_tgz_only.xml")}
    mock.downloads = {"PMC2787494.tar.gz": tgz_bytes}
    install_service(mock)

    resp = client.post("/ncbi/fetch/PMC5334499")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "extracted"
    assert body["source_format"] == "tgz"
    pdf_path = Path(body["pdf_path"])
    assert pdf_path == cache_dir / "PMC5334499.pdf"
    assert pdf_path.read_bytes() == FAKE_PDF


def test_fetch_no_pdf_available(install_service, client):
    """An article with no downloadable resources returns a graceful response."""
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text("oa_none.xml")}
    install_service(mock)

    resp = client.post("/ncbi/fetch/PMC5334499")
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "unavailable"
    assert body["source_format"] == "none"
    assert body["pdf_path"] is None
    assert "No PDF" in body["message"]


def test_fetch_force_redownload(install_service, client):
    """force=True re-downloads even when a cached copy exists."""
    mock = NcbiMock()
    mock.esearch = load_json("esearch_one.json")
    mock.oa_by_id = {"PMC5334499": load_text("oa_pdf.xml")}
    mock.downloads = {"WJR-9-27.PMC5334499.pdf": FAKE_PDF}
    install_service(mock)

    client.post("/ncbi/fetch/PMC5334499")  # populate cache

    resp = client.post("/ncbi/fetch/PMC5334499", params={"force": True})
    assert resp.status_code == 200
    assert resp.json()["status"] == "downloaded"


def test_fetch_falls_back_to_deprecated_path(install_service, client, cache_dir):
    """If the canonical download 404s, the deprecated/ mirror is tried.

    Mirrors PMC's 2026 dataset restructuring where OA links now live under
    ``/pub/pmc/deprecated/``.
    """
    base = NcbiMock()
    base.esearch = load_json("esearch_one.json")
    base.oa_by_id = {"PMC5334499": load_text("oa_pdf.xml")}

    requested: list[str] = []

    def handler(request):  # noqa: ANN001
        path = str(request.url)
        if request.url.path.endswith(".pdf") or "oa_pdf" in path or "oa_package" in path:
            requested.append(path)
            if "deprecated" in path:
                return httpx.Response(200, content=FAKE_PDF)
            return httpx.Response(404, text="gone")
        return base(request)

    install_service(handler)

    resp = client.post("/ncbi/fetch/PMC5334499")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "downloaded"
    assert any("deprecated" not in p for p in requested)
    assert any("deprecated" in p for p in requested)
    assert Path(body["pdf_path"]).read_bytes() == FAKE_PDF
