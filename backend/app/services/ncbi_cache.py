"""NCBI PDF cache seam (PDF source resolution).

The NCBI search/download task (a separate task) downloads PMC Open Access PDFs
into the ``PDF_CACHE_DIR``. This module resolves a ``pmcid`` to such a cached PDF
**without** depending on the NCBI network code — it only knows the on-disk
caching convention so the OCR task can ``POST /ocr/run {pmcid}`` today.

Convention: a PDF for PMC1234567 is cached as ``<PDF_CACHE_DIR>/PMC1234567.pdf``
(with or without the ``PMC`` prefix; the lookup is tolerant of both).

When the cached file does not exist this raises a single, clearly-worded error so
the caller can tell the user to fetch the paper first (that endpoint lives in the
NCBI task).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_pmcid(pmcid: str) -> str:
    """Return the PMC id with a canonical ``PMC`` prefix and no whitespace.

    Accepts ``1234567``, ``PMC1234567``, ``pmc1234567``, `` PMC1234567 ``.
    """
    cleaned = pmcid.strip()
    digits = re.sub(r"(?i)^PMC", "", cleaned)
    if not digits.isdigit():
        raise ValueError(
            f"Invalid pmcid {pmcid!r}: expected digits, optionally prefixed with 'PMC'."
        )
    return f"PMC{digits}"


def resolve_cached_pdf(pmcid: str, pdf_cache_dir: str | Path) -> Path:
    """Resolve a ``pmcid`` to its cached PDF path, or raise ``FileNotFoundError``.

    Raises:
        ValueError: if ``pmcid`` is malformed.
        FileNotFoundError: if the cached PDF is absent (the NCBI task downloads it).
    """
    pmc = normalize_pmcid(pmcid)
    cache = Path(pdf_cache_dir)

    # Tolerate either "PMC123.pdf" or "123.pdf" naming in the cache.
    for candidate in (pmc, pmc[3:]):
        for ext in (".pdf", ".PDF"):
            path = cache / f"{candidate}{ext}"
            if path.is_file():
                return path

    raise FileNotFoundError(
        f"No cached PDF for {pmc} under {cache}. Fetch the paper first via the "
        "NCBI download endpoint (GET /ncbi/papers/{pmcid}/pdf), then retry."
    )
