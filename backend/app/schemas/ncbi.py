"""Request/response schemas for the NCBI / PMC Open Access integration.

These models are the wire contract for the ``/ncbi`` endpoints (see
``app.routers.ncbi``): searching the PMC Open Access subset, resolving a paper's
metadata + download links, and fetching its PDF into the local cache that the
OCR pipeline (``app.routers.ocr``) reads from.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Author(BaseModel):
    """A single paper author."""

    name: str = Field(..., description="Author display name.")
    initials: str = Field(default="", description="Author initials (when known).")


class PaperSummary(BaseModel):
    """A single search-result summary."""

    pmcid: str = Field(..., description="PubMed Central ID, e.g. 'PMC1234567'.")
    pmid: str = Field(default="", description="PubMed ID (when available).")
    doi: str = Field(default="", description="Digital Object Identifier (when available).")
    title: str = Field(default="", description="Article title.")
    authors: list[Author] = Field(default_factory=list, description="List of authors.")
    journal: str = Field(default="", description="Full journal name.")
    year: str = Field(default="", description="Publication year.")
    abstract_snippet: str = Field(
        default="",
        description="Short excerpt of the abstract (best effort; may be empty).",
    )


class SearchResponse(BaseModel):
    """Response for GET /ncbi/search."""

    query: str = Field(..., description="The query string that was searched.")
    page: int = Field(..., description="The 1-based page number returned.")
    page_size: int = Field(..., description="Number of results requested per page.")
    total_results: int = Field(..., description="Total number of matching records in PMC.")
    total_pages: int = Field(..., description="Total number of pages available.")
    results: list[PaperSummary] = Field(
        default_factory=list, description="Summaries for this page."
    )


class DownloadLink(BaseModel):
    """A downloadable resource resolved from the PMC OA service."""

    format: Literal["pdf", "tgz"] = Field(..., description="Resource format.")
    url: HttpUrl = Field(..., description="Download URL.")
    updated: str = Field(default="", description="Last-updated timestamp from PMC.")


class PaperDetail(BaseModel):
    """Response for GET /ncbi/paper/{pmcid}."""

    pmcid: str
    pmid: str = ""
    doi: str = ""
    title: str = ""
    authors: list[Author] = Field(default_factory=list)
    journal: str = ""
    year: str = ""
    license: str = Field(default="", description="License terms reported by PMC OA.")
    citation: str = Field(default="", description="Citation string reported by PMC OA.")
    retracted: bool = Field(default=False, description="Whether the article is retracted.")
    abstract_snippet: str = ""
    downloads: list[DownloadLink] = Field(
        default_factory=list,
        description="Resolved download links (PDF preferred, then tgz package).",
    )


class FetchResponse(BaseModel):
    """Response for POST /ncbi/fetch/{pmcid}."""

    pmcid: str
    status: Literal["cached", "downloaded", "extracted", "unavailable"] = Field(
        ..., description="Outcome of the fetch operation."
    )
    source_format: Literal["pdf", "tgz", "none"] = Field(
        ..., description="The upstream source the PDF came from."
    )
    pdf_path: str | None = Field(
        default=None,
        description="Absolute local path to the cached PDF (None when unavailable).",
    )
    filename: str | None = Field(default=None, description="Name of the cached PDF file.")
    size_bytes: int | None = Field(default=None, description="Size of the cached PDF in bytes.")
    message: str = Field(default="", description="Human-readable detail about the operation.")
