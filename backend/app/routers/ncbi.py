"""NCBI / PubMed Central Open Access router.

Exposes discovery and retrieval of PMC Open Access papers:

* ``GET  /ncbi/search``          — search the PMC Open Access subset.
* ``GET  /ncbi/paper/{pmcid}``   — metadata + download links for a paper.
* ``POST /ncbi/fetch/{pmcid}``   — download (or reuse the cached) PDF.

PDFs are cached under the shared ``NCBI_CACHE_DIR`` (the same directory the OCR
pipeline reads), so a fetched paper is immediately consumable by
``POST /ocr/run {pmcid}``.

A single :class:`~app.services.ncbi.NcbiService` (and its pooled ``httpx``
client) is created per settings instance and reused; tests may override
``get_ncbi_service`` via FastAPI's ``dependency_overrides``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.schemas.ncbi import FetchResponse, PaperDetail, SearchResponse
from app.services.ncbi import NcbiError, NcbiService

router = APIRouter(prefix="/ncbi", tags=["ncbi"])


# --------------------------------------------------------------------------- #
# Dependency providers
# --------------------------------------------------------------------------- #
#
# A single NcbiService is created per settings instance and reused. Using a
# module-level cache keyed on the (immutable) base settings keeps one shared
# httpx.AsyncClient alive for the process, which is what we want for pooling.
# Tests may override ``get_ncbi_service`` via FastAPI's dependency_overrides.

_service_cache: dict[int, NcbiService] = {}


async def get_ncbi_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> NcbiService:
    """Return a process-wide :class:`NcbiService` for the current settings."""
    key = id(settings)
    service = _service_cache.get(key)
    if service is None:
        service = NcbiService(settings)
        _service_cache[key] = service
    return service


NcbiServiceDep = Annotated[NcbiService, Depends(get_ncbi_service)]


def _raise_ncbi_error(exc: NcbiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


async def close_ncbi_services() -> None:
    """Close pooled NcbiService httpx clients (called on app shutdown)."""
    for service in list(_service_cache.values()):
        await service.aclose()
    _service_cache.clear()


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Search the PMC Open Access subset",
    description=(
        "Search PubMed Central (PMC) Open Access papers via NCBI E-utilities. "
        "Runs ESearch against the `pmc` database (automatically filtered to "
        "`open access[filter]`) and ESummary to return pmcid, title, authors, "
        "journal, year and an abstract snippet."
    ),
)
async def search_papers(
    service: NcbiServiceDep,
    query: Annotated[str, Query(description="Free-text search query (Entrez syntax).")],
    page: Annotated[int, Query(ge=1, description="1-based page number.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=100, description="Results per page (max 100).")
    ] = 20,
) -> SearchResponse:
    try:
        return await service.search(query=query, page=page, page_size=page_size)
    except NcbiError as exc:
        _raise_ncbi_error(exc)
        raise  # pragma: no cover - _raise_ncbi_error always raises


@router.get(
    "/paper/{pmcid}",
    response_model=PaperDetail,
    summary="Get metadata + download links for a PMC paper",
    description=(
        "Returns article metadata plus full-text download URL(s) resolved "
        "through the PMC OA Web Service "
        "(https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi)."
    ),
)
async def get_paper(service: NcbiServiceDep, pmcid: str) -> PaperDetail:
    try:
        return await service.get_paper(pmcid)
    except NcbiError as exc:
        _raise_ncbi_error(exc)
        raise  # pragma: no cover


@router.post(
    "/fetch/{pmcid}",
    response_model=FetchResponse,
    summary="Download (or reuse the cached) PDF for a PMC paper",
    description=(
        "Resolves the PDF via the PMC OA service and downloads it into the "
        "local cache directory (`NCBI_CACHE_DIR`). If only a `.tar.gz` package "
        "exists, it is downloaded and the embedded PDF is extracted. Returns "
        "the local file path and basic info. Handles 'no PDF available' "
        "gracefully with an `unavailable` status."
    ),
)
async def fetch_paper(
    service: NcbiServiceDep,
    pmcid: str,
    force: Annotated[
        bool, Query(description="Force re-download even if a cached PDF exists.")
    ] = False,
) -> FetchResponse:
    try:
        return await service.fetch_paper(pmcid, force=force)
    except NcbiError as exc:
        _raise_ncbi_error(exc)
        raise  # pragma: no cover

