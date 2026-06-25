"""Tests for PyMuPDF PDF→PNG rendering (app.services.pdf)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.pdf import pdf_to_images


def test_pdf_to_images_produces_one_png_per_page(sample_pdf: Path) -> None:
    pages = pdf_to_images(sample_pdf, dpi=150)
    assert len(pages) == 2
    for path in pages:
        assert path.endswith(".png")
        assert Path(path).is_file()


def test_pdf_to_images_pages_are_sequentially_named(multipage_pdf: Path) -> None:
    pages = pdf_to_images(multipage_pdf, dpi=72)
    names = [Path(p).name for p in pages]
    assert names == ["page_0001.png", "page_0002.png", "page_0003.png"]


def test_pdf_to_images_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        pdf_to_images(tmp_path / "does_not_exist.pdf")


def test_pdf_to_images_rejects_bad_dpi(sample_pdf: Path) -> None:
    with pytest.raises(ValueError):
        pdf_to_images(sample_pdf, dpi=0)


def test_pdf_to_images_higher_dpi_larger_file(sample_pdf: Path) -> None:
    low = pdf_to_images(sample_pdf, dpi=72)
    high = pdf_to_images(sample_pdf, dpi=300)
    assert Path(high[0]).stat().st_size > Path(low[0]).stat().st_size
