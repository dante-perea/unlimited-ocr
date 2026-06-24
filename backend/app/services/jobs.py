"""In-process async job runner for slow OCR inference.

OCR over a multi-page PDF is slow (minutes on a GPU), so ``POST /ocr/run`` does
not block: it enqueues a job, returns an id immediately, and the client polls
``GET /ocr/status/{job_id}``. This module provides that job store + a thread
pool that runs the blocking model inference off the event loop.

The store is in-memory (single-process). That is sufficient for a local app with
a single worker; it keeps the dependency surface small and avoids a database.

A :class:`JobRunner` is created once and stashed on ``app.state`` (see
``app.main`` lifespan). Routers grab it via ``request.app.state.job_runner``.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from app.schemas.ocr import OcrJobStatus, OcrResult

logger = logging.getLogger(__name__)

# Job lifecycle states.
QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"


@dataclass
class _Job:
    job_id: str
    status: str = QUEUED
    error: str | None = None
    error_code: str | None = None
    result: OcrResult | None = None
    future: Future[Any] | None = field(default=None, repr=False)


class JobRunner:
    """Run blocking callables in a thread pool and track them by id."""

    def __init__(self, max_workers: int = 1) -> None:
        # A single worker serializes GPU jobs (a model typically can't serve
        # concurrent requests). Bump for CPU/mock or batch inference.
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: dict[str, _Job] = {}

    # -- submission -------------------------------------------------------- #

    def submit(self, fn: Callable[..., OcrResult], *args: Any, **kwargs: Any) -> str:
        """Enqueue ``fn(*args, **kwargs)`` and return its job id immediately."""
        job_id = uuid.uuid4().hex
        job = _Job(job_id=job_id)

        def _run() -> OcrResult:
            job.status = RUNNING
            return fn(*args, **kwargs)

        future = self._executor.submit(self._wrap(job, _run))
        job.future = future
        self._jobs[job_id] = job
        logger.info("Enqueued OCR job %s", job_id)
        return job_id

    def _wrap(self, job: _Job, fn: Callable[[], OcrResult]) -> Callable[[], None]:
        def runner() -> None:
            try:
                result = fn()
                job.result = result
                job.status = COMPLETED
                logger.info("OCR job %s completed (%d page(s)).", job.job_id, result.n_pages)
            except Exception as exc:  # noqa: BLE001 - we surface all failures to the job status
                job.error = str(exc)
                job.error_code = getattr(exc, "error_code", None)
                job.status = FAILED
                logger.error(
                    "OCR job %s failed: %s\n%s",
                    job.job_id,
                    exc,
                    traceback.format_exc(),
                )

        return runner

    # -- inspection -------------------------------------------------------- #

    def status(self, job_id: str) -> OcrJobStatus | None:
        """Return the public status snapshot for ``job_id`` (None if unknown)."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return OcrJobStatus(
            job_id=job.job_id,
            status=job.status,
            error=job.error,
            error_code=job.error_code,
            result=job.result,
        )

    def shutdown(self) -> None:
        """Shut the pool down (called on app shutdown)."""
        self._executor.shutdown(wait=False, cancel_futures=True)
