"""FastAPI application entry point.

Run locally with::

    uvicorn app.main:app --reload --port 8000

The app exposes ``/health`` today; the ``ncbi`` and ``ocr`` routers are mounted
as empty seams that later tasks fill in.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import health, ncbi, ocr
from app.utils.device import detect_device

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Resolve the compute device once at startup and stash it on app.state."""
    settings = get_settings()
    device = detect_device(settings.device)
    app.state.device = device
    logger.info(
        "%s started (environment=%s, device=%s)",
        settings.app_name,
        settings.environment,
        device,
    )
    yield


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
