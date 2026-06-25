"""FastAPI application entry point.

Run locally with::

    uvicorn app.main:app --reload --port 8000

The app exposes ``/health`` today; the ``ncbi`` and ``ocr`` routers are mounted
as empty seams that later tasks fill in.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health, ncbi, ocr
from app.routers.ncbi import close_ncbi_services
from app.services.jobs import JobRunner
from app.utils.device import detect_device

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Resolve the compute device and start the OCR job runner at startup."""
    settings = get_settings()
    device = detect_device(settings.device)
    app.state.device = device

    # Export the weights cache dir so transformers/HuggingFace uses it. This keeps
    # the multi-GB model weights under the configured HF_HOME (see .env.example).
    if settings.hf_home:
        os.environ.setdefault("HF_HOME", settings.hf_home)

    # Single-worker pool: a model typically can't serve concurrent GPU requests.
    app.state.job_runner = JobRunner(max_workers=1)

    # Ensure the shared PDF cache dir exists (used by both /ncbi/fetch and /ocr/run).
    Path(settings.ncbi_cache_dir_resolved).mkdir(parents=True, exist_ok=True)

    logger.info(
        "%s started (environment=%s, device=%s, ocr_mock=%s)",
        settings.app_name,
        settings.environment,
        device,
        settings.ocr_mock,
    )
    yield
    app.state.job_runner.shutdown()
    await close_ncbi_services()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Feature routers. Adding /ncbi and /ocr endpoints later needs no changes here.
    app.include_router(health.router)
    app.include_router(ncbi.router)
    app.include_router(ocr.router)

    return app


app = create_app()
