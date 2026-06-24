"""Unlimited-OCR router.

Endpoints:

* ``POST /ocr/run`` — accept a ``pmcid`` (resolved against the NCBI PDF cache) or
  a cached ``pdf_path``; enqueue an async OCR job and return its id immediately
  (inference is slow). Body: :class:`~app.schemas.ocr.OcrRunRequest`.
* ``GET  /ocr/status/{job_id}`` — poll a job's status/result.

Inference runs on a worker thread via the shared :class:`~app.services.jobs.JobRunner`
(stashed on ``app.state`` by ``app.main``). The model is loaded lazily (once) and
selected with the foundation device-detection utility (cuda > mps > cpu), or
replaced by mock output when ``OCR_MOCK=1``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.schemas.ocr import OcrJobStatus, OcrRunAccepted, OcrRunRequest
from app.services.jobs import JobRunner
from app.services.ocr_model import GpuRequirementError
from app.services.ocr_orchestration import OcrInputError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["ocr"])


def _runner(request: Request) -> JobRunner:
    """Return the app-level job runner set up in the lifespan."""
    runner = getattr(request.app.state, "job_runner", None)
    if runner is None:  # pragma: no cover - lifespan always sets it
        raise HTTPException(status_code=503, detail="OCR job runner is not ready.")
    return runner


@router.post(
    "/run",
    response_model=OcrRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run OCR on a PMC id or cached PDF (async)",
)
def run(request: Request, body: OcrRunRequest) -> OcrRunAccepted:
    """Enqueue an OCR job. Returns the job id + the path to poll for results."""
    settings = get_settings()
    if not body.pmcid and not body.pdf_path:
        raise HTTPException(
            status_code=422,
            detail="Provide either 'pmcid' or 'pdf_path'.",
        )

    # Apply an optional per-request DPI override (shallow copy, not the cached one).
    if body.dpi is not None:
        settings = settings.model_copy(update={"ocr_pdf_dpi": body.dpi})

    try:
        job_id = _runner(request).submit(
            # Imported here so a bad import surfaces only when OCR is actually used,
            # keeping the app importable on hosts without the ML stack.
            _build_job(),
            settings=settings,
            pmcid=body.pmcid,
            pdf_path=body.pdf_path,
        )
    except Exception:
        logger.exception("Failed to enqueue OCR job.")
        raise

    return OcrRunAccepted(job_id=job_id, status="queued", poll=f"/ocr/status/{job_id}")


@router.get(
    "/status/{job_id}",
    response_model=OcrJobStatus,
    summary="Poll an OCR job's status and result",
)
def get_status(job_id: str, request: Request) -> OcrJobStatus:
    """Return the current status of an OCR job (and its result when completed)."""
    snapshot = _runner(request).status(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Unknown job id: {job_id}")

    # Translate a GPU/CUDA requirement failure into a clear 422 with an actionable
    # body so the frontend can surface it instead of a 500.
    if snapshot.status == "failed" and snapshot.error_code == GpuRequirementError.error_code:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": snapshot.error_code,
                "message": snapshot.error or "A CUDA GPU is required for real OCR.",
            },
        )
    return snapshot


def _build_job():
    """Return the OCR job callable (lazy import to keep the module importable)."""
    from app.services.ocr_orchestration import run_ocr_job

    return run_ocr_job


__all__ = ["router", "OcrInputError"]

