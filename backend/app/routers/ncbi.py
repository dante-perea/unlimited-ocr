"""NCBI / PubMed Central Open Access router.

Endpoints to search and fetch free-access papers from the PubMed Central (PMC)
Open Access subset via NCBI E-utilities and the PMC OA Web Service. See
``app.services.ncbi`` for the implementation; this module only wires HTTP.

    GET  /ncbi/search?query=...&page=...   search PMC Open Access papers
    GET  /ncbi/paper/{pmcid}               metadata + full-text download URLs
    POST /ncbi/fetch/{pmcid}               download/extract the PDF into the cache
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.ncbi import FetchResponse, PaperDetail, SearchResponse
from app.services.ncbi import NcbiError, NcbiService, get_ncbi_service

router = APIRouter(prefix="/ncbi", tags=["ncbi"])


def _raise_ncbi_error(exc: NcbiError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)


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
    service: Annotated[NcbiService, Depends(get_ncbi_service)],
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


@router.get(
    "/paper/{pmcid}",
    response_model=PaperDetail,
    summary="Get metadata + download links for a PMC paper",
    description=(
        "Returns article metadata plus full-text download URL(s) resolved through "
        "the PMC OA Web Service (https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi)."
    ),
)
async def get_paper(
    service: Annotated[NcbiService, Depends(get_ncbi_service)],
    pmcid: str,
) -> PaperDetail:
    try:
        return await service.get_paper(pmcid)
    except NcbiError as exc:
        _raise_ncbi_error(exc)


@router.post(
    "/fetch/{pmcid}",
    response_model=FetchResponse,
    summary="Download (or reuse the cached) PDF for a PMC paper",
    description=(
        "Resolves the PDF via the PMC OA service and downloads it into the local "
        "cache (`PDF_CACHE_DIR`). If only a `.tar.gz` package exists, it is "
        "downloaded and the embedded PDF is extracted. Returns the local file path "
        "and basic info. The cached PDF is what the OCR pipeline consumes by "
        "PMCID. Handles 'no PDF available' gracefully with an `unavailable` status."
    ),
)
async def fetch_paper(
    service: Annotated[NcbiService, Depends(get_ncbi_service)],
    pmcid: str,
    force: Annotated[
        bool, Query(description="Force re-download even if a cached PDF exists.")
    ] = False,
) -> FetchResponse:
    try:
        return await service.fetch_paper(pmcid, force=force)
    except NcbiError as exc:
        _raise_ncbi_error(exc)

