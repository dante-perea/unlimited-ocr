"""Request/response schemas for the OCR pipeline.

These models are the wire contract for ``POST /ocr/run`` and
``GET /ocr/status/{job_id}`` (see ``app.routers.ocr``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class OcrRunRequest(BaseModel):
    """Body for ``POST /ocr/run``.

    Provide *either* a ``pmcid`` (resolved against the NCBI PDF cache) *or* an
    explicit ``pdf_path`` on disk. When both are given, ``pdf_path`` wins.
    """

    pmcid: str | None = Field(
        default=None,
        description="PubMed Central id (with or without the 'PMC' prefix). "
        "Resolved against the cached PDF dir (see PDF_CACHE_DIR).",
    )
    pdf_path: str | None = Field(
        default=None,
        description="Absolute or cwd-relative path to a PDF on disk. Takes "
        "priority over pmcid when both are supplied.",
    )
    dpi: int | None = Field(
        default=None,
        description="Override the PDF rasterization DPI (default from settings).",
    )


class OcrRunAccepted(BaseModel):
    """Immediate response from ``POST /ocr/run``: the id of the queued job."""

    job_id: str
    status: str = "queued"
    poll: str = Field(description="Relative path to poll for status/result.")


class OcrPage(BaseModel):
    """One page of extracted text/markdown."""

    page_index: int = Field(description="Zero-based page index.")
    text: str = Field(default="", description="Markdown/text extracted for the page.")


class Facts(BaseModel):
    """Structured facts derived from the parsed full text.

    ``extractor`` names the strategy that produced these (``"heuristic"`` for the
    built-in baseline). Fields are best-effort — a later/LLM extractor can fill
    them more completely via the extension point in ``app.services.facts``.
    """

    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    doi: str | None = None
    pmcid: str | None = None
    extractor: str = "heuristic"


class OcrResult(BaseModel):
    """The completed OCR payload: per-page text, full text, and facts."""

    pages: list[OcrPage]
    full_text: str
    facts: Facts
    n_pages: int
    device: str = Field(description="Compute device used (cuda/mps/cpu/mock).")
    mock: bool = Field(default=False, description="True if canned/mock output was used.")


class OcrJobStatus(BaseModel):
    """Status (and, when complete, result) of an OCR job."""

    job_id: str
    status: str = Field(description="One of: queued, running, completed, failed.")
    error: str | None = None
    error_code: str | None = None
    result: OcrResult | None = None
