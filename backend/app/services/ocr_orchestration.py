"""High-level OCR orchestration: resolve source PDF → load model → run pipeline.

This is the callable the router submits to the :class:`~app.services.jobs.JobRunner`.
It deliberately concentrates all the "decide which PDF, load which model, run the
pipeline, surface failures" logic in one place so the router stays a thin HTTP
adapter and the pipeline (:mod:`app.services.ocr_pipeline`) stays model-agnostic.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.config import Settings
from app.schemas.ocr import OcrResult
from app.services.model_types import ModelBundle
from app.services.ncbi_cache import normalize_pmcid, resolve_cached_pdf
from app.services.ocr_model import get_model
from app.services.ocr_pipeline import run_ocr

logger = logging.getLogger(__name__)


class OcrInputError(ValueError):
    """Raised when the request provides neither a valid pmcid nor a pdf_path."""

    error_code = "bad_input"


def resolve_pdf_source(
    *,
    pmcid: str | None,
    pdf_path: str | None,
    pdf_cache_dir: str,
) -> tuple[Path, str | None]:
    """Resolve the request inputs to a concrete PDF path + normalized pmcid.

    ``pdf_path`` wins when both are supplied. Otherwise ``pmcid`` is resolved
    against the on-disk PDF cache (see :mod:`app.services.ncbi_cache`).

    Raises:
        OcrInputError: if neither input is usable.
        FileNotFoundError: if a referenced PDF/cache entry does not exist.
        ValueError: if ``pmcid`` is malformed.
    """
    if pdf_path:
        path = Path(pdf_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found: {path}")
        # Keep a pmcid if the caller also passed one (for facts), else None.
        resolved_pmcid = normalize_pmcid(pmcid) if pmcid else None
        return path, resolved_pmcid

    if pmcid:
        normalized = normalize_pmcid(pmcid)
        return resolve_cached_pdf(normalized, pdf_cache_dir), normalized

    raise OcrInputError("Provide either 'pmcid' or 'pdf_path'.")


def run_ocr_job(
    *,
    settings: Settings,
    pmcid: str | None = None,
    pdf_path: str | None = None,
) -> OcrResult:
    """Load the model (lazy singleton) and run OCR over the resolved PDF.

    This is the function submitted to the job runner. All heavy work (model load
    + inference) happens here, on a worker thread.
    """
    pdf, resolved_pmcid = resolve_pdf_source(
        pmcid=pmcid,
        pdf_path=pdf_path,
        pdf_cache_dir=settings.pdf_cache_dir_resolved,
    )

    model_bundle: ModelBundle = get_model(settings)
    logger.info(
        "Starting OCR on %s (device=%s, mock=%s)",
        os.path.basename(str(pdf)),
        model_bundle[2],
        model_bundle[2] == "mock",
    )
    return run_ocr(pdf, model_bundle, settings=settings, pmcid=resolved_pmcid)
