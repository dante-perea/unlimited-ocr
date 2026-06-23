"""NCBI / PubMed Central Open Access router (seam for a later task).

This router is intentionally empty for now. The task that implements PMC
Open Access search and PDF download will add endpoints here — the router is
already created and mounted in ``app.main`` so no app wiring needs to change.

Planned endpoints (illustrative):
    GET /ncbi/search?term=...        -> search PMC Open Access
    GET /ncbi/papers/{pmcid}         -> metadata for a paper
    GET /ncbi/papers/{pmcid}/pdf     -> download / stream the PDF
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ncbi", tags=["ncbi"])

# TODO(ncbi-task): implement search + fetch endpoints on `router`.
