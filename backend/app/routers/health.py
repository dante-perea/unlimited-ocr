"""Health-check router."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    """Liveness probe.

    Returns ``status: ok`` plus the resolved compute device (detected once at
    startup and stored on ``app.state``).
    """
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "device": getattr(request.app.state, "device", "unknown"),
    }
