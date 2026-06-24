"""Shared pytest fixtures for the backend tests.

The whole suite runs in mock/offline mode (``OCR_MOCK=1``) so it never needs
torch, transformers, or model weights. Endpoint tests additionally reset the
in-memory settings cache per-test so ``model_copy`` overrides / env flags don't
leak between tests.
"""

from __future__ import annotations

import os
from pathlib import Path

# Force mock/offline mode for the entire suite before any app import.
os.environ["OCR_MOCK"] = "1"

import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services import ocr_model  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_caches():
    """Reset the settings cache + model singleton before each test."""
    get_settings.cache_clear()
    ocr_model.reset_model()
    yield
    get_settings.cache_clear()
    ocr_model.reset_model()


# --------------------------------------------------------------------------- #
# Synthetic PDF fixtures (built with PyMuPDF — no network/files on disk needed).
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
