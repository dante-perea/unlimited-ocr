"""Unlimited-OCR router (seam for a later task).

This router is intentionally empty for now. The task that wires up the local
Unlimited-OCR pipeline will add endpoints here — the router is already created
and mounted in ``app.main`` so no app wiring needs to change.

Planned endpoints (illustrative):
    POST /ocr/run        -> run OCR on a downloaded PDF, return text + facts
    GET  /ocr/jobs/{id}  -> poll a long-running OCR job
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ocr", tags=["ocr"])

# TODO(ocr-task): implement OCR endpoints on `router` using app.utils.device
# to select cuda/mps/cpu and the vendored Unlimited-OCR model.
