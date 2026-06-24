"""Structured-facts extraction from parsed text.

This module turns the OCR'd markdown/text for a document into a small set of
structured fields (:class:`~app.schemas.ocr.Facts`): title, authors, abstract,
key findings, entities, tables, doi, pmcid.

The default extractor is a deterministic **heuristic baseline** (regex + light
structural parsing of markdown). It is intentionally simple and never blocks the
pipeline on perfection. It is the only extractor shipped here, but the design
exposes a clear **extension point** so a richer extractor (e.g. an LLM call or an
NLP pipeline) can be plugged in without touching the OCR pipeline or router:

    from app.services.facts import register_fact_extractor, FactExtractor

    @register_fact_extractor("llm")
    def llm_extractor(text: str, *, pmcid: str | None = None) -> Facts:
        ...   # call your LLM / NER / table parser here
        return Facts(..., extractor="llm")

Then set ``FACTS_EXTRACTOR=llm`` to use it. The heuristic baseline stays the
default so the system always works end-to-end.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

from app.schemas.ocr import Facts

# --------------------------------------------------------------------------- #
# Extension point: a registry of named fact extractors.
# --------------------------------------------------------------------------- #

_FACT_EXTRACTORS: dict[str, "FactExtractor"] = {}


class FactExtractor(Protocol):
    """Signature every facts extractor must implement."""

    def __call__(self, text: str, *, pmcid: str | None = None) -> Facts: ...


def register_fact_extractor(name: str) -> Callable[[FactExtractor], FactExtractor]:
    """Decorator to register a facts extractor under ``name`` (the extension point).

    A registered extractor is selected by setting ``FACTS_EXTRACTOR=<name>``.
    """

    def decorator(fn: FactExtractor) -> FactExtractor:
        if name == "heuristic":
            # Reserve "heuristic" for the built-in default below.
            raise ValueError("'heuristic' is reserved for the built-in extractor.")
        _FACT_EXTRACTORS[name] = fn
        return fn

    return decorator


def get_fact_extractor(name: str) -> FactExtractor:
    """Return the registered extractor, falling back to the heuristic baseline."""
    if name == "heuristic" or not name:
        return extract_facts_heuristic
    if name in _FACT_EXTRACTORS:
        return _FACT_EXTRACTORS[name]
    raise KeyError(
        f"Unknown facts extractor {name!r}. Registered: {sorted(_FACT_EXTRACTORS)} "
        "(or 'heuristic'). Use app.services.facts.register_fact_extractor to add one."
    )


def extract_facts(text: str, *, pmcid: str | None = None, extractor: str = "heuristic") -> Facts:
    """Run the configured facts extractor on ``text``.

    This is the single entry point used by the OCR pipeline.
    """
    return get_fact_extractor(extractor)(text, pmcid=pmcid)

# --------------------------------------------------------------------------- #
# Heuristic baseline extractor.
# --------------------------------------------------------------------------- #

# DOI: 10.NNNN/... (the capturing group is the whole DOI string)
_DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s\"')]+)", re.IGNORECASE)
# PMC1234567 (case-insensitive PMC prefix + digits)
_PMCID_RE = re.compile(r"(PMC\d{4,9})\b", re.IGNORECASE)
# A markdown table block: a header row, a delimiter row, then body rows.
_TABLE_RE = re.compile(
    r"(?:^[ \t]*\|[^\n]*\|[^\n]*\n)(?:^[ \t]*\|[\s:|-]+\|[^\n]*\n)(?:^[ \t]*\|[^\n]*\|[^\n]*\n?)+",
    re.MULTILINE,
)
_HEADING_RE = re.compile(r"^[ \t]*#{1,6}\s+(.+?)\s*$", re.MULTILINE)
# Gene/protein-ish token: all-caps acronym, or dashed, or alnum-mixed.
_ENTITY_CANDIDATES_RE = re.compile(
    r"\b([A-Z][A-Z0-9-]{2,}|[A-Za-z]+-[A-Za-z0-9]+|[A-Za-z]+\d+[A-Za-z]*)\b"
)

_STOPWORDS = {"the", "and", "for", "with", "doi", "pmcid", "table", "figure", "from", "this"}


def _clean(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    return s or None


def _split_authors(line: str) -> list[str]:
    """Split an author byline on commas/semicolons/ampersands/and."""
    parts = re.split(r"[,;]|&|\band\b", line)
    names = [p.strip(" .,;") for p in parts]
    # Keep only entries that look like a name to avoid capturing affiliations.
    return [n for n in names if n and 2 <= len(n) <= 80 and re.search(r"[A-Za-z]", n)]


def extract_facts_heuristic(text: str, *, pmcid: str | None = None) -> Facts:
    """Best-effort, dependency-free structured extraction from parsed text."""
    if not text:
        return Facts(extractor="heuristic", pmcid=pmcid)

    lines = [ln.rstrip() for ln in text.splitlines()]

    # --- Title: first markdown heading, else first non-empty non-meta line. ---
    title: str | None = None
    for ln in lines:
        m = _HEADING_RE.match(ln)
        if m:
            title = m.group(1).strip()
            break
    if not title:
        for ln in lines:
            s = ln.strip()
            if not s or s.startswith("|") or s.startswith("#"):
                continue
            title = s
            break

    # --- Authors: first byline-like line shortly after the title. ---
    authors: list[str] = []
    title_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == (title or "").strip()), 0
    )
    for ln in lines[title_idx + 1 : title_idx + 6]:
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith("|"):
            continue
        candidates = _split_authors(s)
        if candidates and ("," in s or "&" in s or " and " in s.lower()):
            authors = candidates
            break

    # --- Abstract: text under "## Abstract" until the next heading. ---
    abstract: str | None = None
    for i, ln in enumerate(lines):
        if re.match(r"^\s*#{1,6}\s*abstract\b", ln.strip(), re.IGNORECASE):
            block: list[str] = []
            for nxt in lines[i + 1 :]:
                if re.match(r"^\s*#{1,6}\s*\S", nxt):
                    break
                if nxt.strip():
                    block.append(nxt.strip())
            abstract = _clean(" ".join(block))
            break

    # --- Key findings: result/conclusion-flavored sentences. ---
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
    finding_cues = (
        "we show", "we find", "we found", "we demonstrate", "our results",
        "our findings", "in conclusion", "this suggests", "these results",
    )
    key_findings: list[str] = []
    for sent in sentences:
        low = sent.lower()
        if any(cue in low for cue in finding_cues) and 30 <= len(sent) <= 400:
            key_findings.append(sent.strip())
            if len(key_findings) >= 5:
                break

    # --- Entities: dedup gene/protein/acronym candidates. ---
    entities: list[str] = []
    seen: set[str] = set()
    for m in _ENTITY_CANDIDATES_RE.finditer(text):
        token = m.group(1)
        if token.lower() in _STOPWORDS:
            continue
        key = token.lower()
        if key not in seen:
            seen.add(key)
            entities.append(token)
        if len(entities) >= 20:
            break

    # --- Tables: capture markdown table blocks verbatim (trimmed). ---
    tables = [block.strip() for block in _TABLE_RE.findall(text + "\n")][:5]

    # --- DOI / PMCID from explicit markers, fall back to first match. ---
    doi = None
    doi_marker = re.search(r"(?i)\bDOI[:\s]*" + _DOI_RE.pattern, text)
    if doi_marker:
        doi = _clean(doi_marker.group(1))
    if not doi:
        dm = _DOI_RE.search(text)
        doi = _clean(dm.group(1)) if dm else None

    found_pmcid = pmcid
    if not found_pmcid:
        pm = _PMCID_RE.search(text)
        found_pmcid = _clean(pm.group(1)) if pm else None
    elif found_pmcid:
        found_pmcid = found_pmcid.upper().replace("PMC", "PMC")

    return Facts(
        title=title,
        authors=authors,
        abstract=abstract,
        key_findings=key_findings,
        entities=entities,
        tables=tables,
        doi=doi,
        pmcid=found_pmcid,
        extractor="heuristic",
    )