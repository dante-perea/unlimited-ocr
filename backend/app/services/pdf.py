"""PDF rasterization via PyMuPDF (fitz).

Renders each PDF page to a PNG at a configurable DPI so the OCR model can consume
page images. This mirrors the ``pdf_to_images`` helper in the upstream
Unlimited-OCR README, returning a list of PNG paths written to a temp directory.

PyMuPDF is a *core* dependency (not the heavy ML stack), so importing this module
works on any host — including the Apple-Silicon dev box and the CI used for tests.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def pdf_to_images(pdf_path: str | os.PathLike[str], *, dpi: int = 300) -> list[str]:
    """Render every page of ``pdf_path`` to a PNG file; return the paths.

    Pages are written as ``page_0001.png``, ``page_0002.png``, ... inside a fresh
    temp directory (created per call). The caller owns cleanup of that directory.

    Args:
        pdf_path: Path to a PDF on disk.
        dpi: Rasterization DPI (72 = PDF "points" unit). Upstream uses 300.

    Returns:
        Ordered list of PNG file paths, one per page.

    Raises:
        FileNotFoundError: if ``pdf_path`` does not exist.
    """
    pdf = Path(pdf_path)
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    import fitz  # PyMuPDF — imported lazily to keep module import cheap/safe.

    if dpi <= 0:
        raise ValueError(f"DPI must be positive, got {dpi}")

    tmp_dir = tempfile.mkdtemp(prefix="pdf_ocr_")
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    paths: list[str] = []
    doc = fitz.open(str(pdf))
    try:
        for index, page in enumerate(doc):
            out = os.path.join(tmp_dir, f"page_{index + 1:04d}.png")
            page.get_pixmap(matrix=matrix).save(out)
            paths.append(out)
    finally:
        doc.close()

    logger.info("Rendered %d page(s) from %s at %d DPI -> %s", len(paths), pdf.name, dpi, tmp_dir)
    return paths
