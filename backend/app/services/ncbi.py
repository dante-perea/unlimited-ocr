"""NCBI integration service: discover + retrieve PMC Open Access papers.

Implements discovery and retrieval of Open-Access papers from PubMed Central
(PMC) using:

* NCBI E-utilities (ESearch + ESummary + EFetch) for searching & metadata.
* The PMC Open Access Web Service (``oa.fcgi``) for resolving download links.
* A local on-disk cache for downloaded PDFs.

All upstream HTTP is performed asynchronously with :mod:`httpx`, and every
E-utility call passes through a rate limiter that respects NCBI's policy
(3 requests/second without an API key, 10/second with one).

The cache directory is shared with the OCR pipeline
(``Settings.ncbi_cache_dir_resolved``) so a PDF fetched here is immediately
consumable by ``POST /ocr/run {pmcid}``.
"""

from __future__ import annotations

import asyncio
import io
import re
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import Settings
from app.schemas.ncbi import (
    Author,
    DownloadLink,
    FetchResponse,
    PaperDetail,
    PaperSummary,
    SearchResponse,
)

# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #


class NcbiError(Exception):
    """Base class for NCBI service errors understood by the API layer."""

    def __init__(self, detail: str, status_code: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class PaperNotFound(NcbiError):
    """Raised when a PMCID cannot be resolved."""

    def __init__(self, pmcid: str) -> None:
        super().__init__(
            f"No PMC Open Access record found for '{pmcid}'.", status_code=404
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_PMC_DIGITS_RE = re.compile(r"\d+")
_ABSTRACT_MAX_CHARS = 300


def normalize_pmcid(pmcid: str) -> str:
    """Return a canonical ``PMC<digits>`` identifier.

    Accepts ``PMC123``, ``123``, ``pmc123`` etc. Raises :class:`NcbiError`
    for anything that does not contain digits.
    """
    match = _PMC_DIGITS_RE.search(pmcid or "")
    if not match:
        raise NcbiError(
            f"Invalid PMC ID '{pmcid}'. Expected e.g. 'PMC5334499' or '5334499'.",
            status_code=400,
        )
    return f"PMC{match.group(0)}"


def _to_https(url: str) -> str:
    """PMC OA links are often ``ftp://``; switch to the HTTPS mirror."""
    if url.lower().startswith("ftp://"):
        return "https://" + url[len("ftp://"):]
    return url


_PMC_PATH_MARKER = "/pub/pmc/"


def candidate_download_urls(url: str) -> list[str]:
    """Build the list of URLs to try when downloading an OA resource.

    The PMC OA service historically returns ``ftp://`` links whose HTTPS
    mirror lives at ``/pub/pmc/<subpath>``. During PMC's dataset restructuring
    files were relocated under a ``deprecated/`` prefix, so we additionally
    offer that path as a fallback. The first entry is always the "canonical"
    HTTPS mirror; subsequent entries are fallbacks tried on 404.
    """
    https_url = _to_https(url)
    candidates = [https_url]
    if _PMC_PATH_MARKER in https_url and "/deprecated/" not in https_url:
        idx = https_url.index(_PMC_PATH_MARKER) + len(_PMC_PATH_MARKER)
        candidates.append(https_url[:idx] + "deprecated/" + https_url[idx:])
    return candidates


def _extract_year(pubdate: str) -> str:
    """Pull a 4-digit year out of a free-form publication date string."""
    match = re.search(r"\d{4}", pubdate or "")
    return match.group(0) if match else ""


def _truncate(text: str, limit: int = _ABSTRACT_MAX_CHARS) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut + "\u2026"


# --------------------------------------------------------------------------- #
# Rate limiting
# --------------------------------------------------------------------------- #


class RateLimiter:
    """Async limiter enforcing a maximum number of calls per second.

    Implemented as a *minimum spacing* scheduler: each :meth:`acquire` reserves
    a slot and ensures successive acquisitions are at least ``1/rate`` seconds
    apart. Because acquisitions are serialized through a lock, this guarantees
    the configured ceiling is never exceeded.
    """

    def __init__(self, rate_per_second: float) -> None:
        self._min_interval = (
            1.0 / rate_per_second if rate_per_second and rate_per_second > 0 else 0.0
        )
        self._lock = asyncio.Lock()
        self._next_slot = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            loop = asyncio.get_event_loop()
            now = loop.time()
            wait = self._next_slot - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = loop.time()
            self._next_slot = max(now, self._next_slot) + self._min_interval


class NcbiService:
    """Stateful service wrapping NCBI E-utilities and the PMC OA service.

    A single :class:`httpx.AsyncClient` is owned by each instance so that
    connection pooling is reused across requests. Instances should be closed
    via :meth:`aclose` when the application shuts down.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.ncbi_request_timeout,
            headers={"User-Agent": settings.ncbi_tool},
            follow_redirects=True,
        )
        self._limiter = RateLimiter(settings.rate_per_second)

    # -- lifecycle -----------------------------------------------------------
    async def aclose(self) -> None:
        await self._client.aclose()

    def _with_default_params(self, params: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "tool": self.settings.ncbi_tool,
            "retmode": "json",
        }
        if self.settings.ncbi_email:
            merged["email"] = self.settings.ncbi_email
        if self.settings.has_api_key:
            merged["api_key"] = self.settings.ncbi_api_key
        merged.update(params)
        return merged

    @staticmethod
    def _status_from(exc: httpx.HTTPError) -> int:
        resp = getattr(exc, "response", None)
        return resp.status_code if resp is not None else 502

    async def _eutils_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Issue a rate-limited E-utility GET and return parsed JSON."""
        params = self._with_default_params(params)
        await self._limiter.acquire()
        url = f"{self.settings.ncbi_eutils_base_url}/{path}"
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise NcbiError(
                f"NCBI E-utilities request failed: {exc}",
                status_code=self._status_from(exc),
            ) from exc
        return resp.json()

    async def _eutils_get_text(self, path: str, params: dict[str, Any]) -> str:
        """Issue a rate-limited E-utility GET and return raw text (for XML)."""
        params = self._with_default_params(params)
        await self._limiter.acquire()
        url = f"{self.settings.ncbi_eutils_base_url}/{path}"
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise NcbiError(
                f"NCBI E-utilities request failed: {exc}",
                status_code=self._status_from(exc),
            ) from exc
        return resp.text

    async def _oa_get_xml(self, pmcid: str) -> ET.Element:
        """Query the PMC OA service for ``pmcid`` and return the parsed root."""
        await self._limiter.acquire()
        try:
            resp = await self._client.get(
                self.settings.ncbi_oa_base_url, params={"id": pmcid}
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise NcbiError(
                f"PMC OA service request failed: {exc}",
                status_code=self._status_from(exc),
            ) from exc
        try:
            return ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise NcbiError(f"Could not parse PMC OA response: {exc}") from exc


    # -- ESearch -------------------------------------------------------------
    async def _esearch_pmc(
        self, query: str, retstart: int, retmax: int
    ) -> tuple[list[str], int]:
        """Run ESearch against the PMC Open Access subset. Returns ``(ids, total)``."""
        term = f"{query} AND open access[filter]"
        data = await self._eutils_get(
            "esearch.fcgi",
            {"db": "pmc", "term": term, "retstart": retstart, "retmax": retmax},
        )
        result = data.get("esearchresult", {})
        if "error" in result:
            raise NcbiError(f"ESearch error: {result['error']}")
        id_list = list(result.get("idlist", []))
        try:
            total = int(result.get("count", 0))
        except (TypeError, ValueError):
            total = 0
        return id_list, total

    # -- ESummary ------------------------------------------------------------
    async def _esummary_pmc(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch ESummary document summaries for a list of PMC UIDs."""
        if not ids:
            return {}
        data = await self._eutils_get(
            "esummary.fcgi",
            {"db": "pmc", "id": ",".join(ids), "version": "2.0"},
        )
        return data.get("result", {})

    # -- EFetch (abstracts, best effort) ------------------------------------
    async def _fetch_abstracts(self, pmids: list[str]) -> dict[str, str]:
        """Fetch PubMed abstracts -> ``{pmid: text}``. Failures are swallowed."""
        if not pmids:
            return {}
        try:
            text = await self._eutils_get_text(
                "efetch.fcgi",
                {
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "rettype": "abstract",
                    "retmode": "xml",
                },
            )
        except NcbiError:
            return {}
        return self._parse_pubmed_abstracts(text)

    @staticmethod
    def _parse_pubmed_abstracts(xml_text: str) -> dict[str, str]:
        """Parse a PubMed EFetch abstract XML payload into a pmid->text map."""
        out: dict[str, str] = {}
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return out
        for article in root.iter("PubmedArticle"):
            pmid_el = article.find(".//PMID")
            if pmid_el is None or not (pmid_el.text or "").strip():
                continue
            pmid = pmid_el.text.strip()
            parts: list[str] = []
            for abs_el in article.iter("AbstractText"):
                label = abs_el.attrib.get("Label")
                chunk = "".join(abs_el.itertext()).strip()
                if not chunk:
                    continue
                parts.append(f"{label}: {chunk}" if label else chunk)
            if parts:
                out[pmid] = " ".join(parts)
        return out


    # -- summary mapping -----------------------------------------------------
    @staticmethod
    def _doc_to_summary(
        uid: str, doc: dict[str, Any], abstracts: dict[str, str]
    ) -> PaperSummary:
        article_ids = doc.get("articleids", []) or []
        pmcid = ""
        pmid = ""
        doi = ""
        for entry in article_ids:
            idtype = (entry.get("idtype") or "").lower()
            value = str(entry.get("value") or entry.get("id") or "").strip()
            if idtype in ("pmc", "pmcid") and value:
                pmcid = value
            elif idtype in ("pubmed", "pmid") and value:
                pmid = value
            elif idtype == "doi" and value:
                doi = value
        if not pmcid:
            pmcid = f"PMC{uid}"

        authors = [
            Author(
                name=str(a.get("name") or "").strip(),
                initials=str(a.get("inititals") or a.get("initials") or "").strip(),
            )
            for a in (doc.get("authors") or [])
            if str(a.get("name") or "").strip()
        ]

        full_abstract = abstracts.get(pmid, "")
        snippet = _truncate(full_abstract) if full_abstract else ""

        return PaperSummary(
            pmcid=pmcid,
            pmid=pmid,
            doi=doi,
            title=str(doc.get("title") or "").strip(),
            authors=authors,
            journal=str(doc.get("fulljournalname") or doc.get("source") or "").strip(),
            year=_extract_year(str(doc.get("pubdate") or "")),
            abstract_snippet=snippet,
        )

    # -- public API: search --------------------------------------------------
    async def search(
        self, query: str, page: int = 1, page_size: int = 20
    ) -> SearchResponse:
        """Search the PMC Open Access subset and return paginated summaries."""
        if not query or not query.strip():
            raise NcbiError("A non-empty 'query' is required.", status_code=400)
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        retstart = (page - 1) * page_size

        ids, total = await self._esearch_pmc(query.strip(), retstart, page_size)

        summaries: list[PaperSummary] = []
        if ids:
            result = await self._esummary_pmc(ids)
            uids = result.get("uids", [])
            pmids: list[str] = []
            docs: dict[str, dict[str, Any]] = {}
            for uid in uids:
                doc = result.get(uid, {})
                if not isinstance(doc, dict) or "error" in doc:
                    continue
                docs[uid] = doc
                for entry in doc.get("articleids", []) or []:
                    if (entry.get("idtype") or "").lower() in ("pubmed", "pmid"):
                        val = str(entry.get("value") or entry.get("id") or "").strip()
                        if val:
                            pmids.append(val)
                        break
            abstracts = await self._fetch_abstracts(pmids)
            for uid in uids:
                doc = docs.get(uid)
                if doc is None:
                    continue
                summaries.append(self._doc_to_summary(uid, doc, abstracts))

        total_pages = (total + page_size - 1) // page_size if total else 0
        return SearchResponse(
            query=query,
            page=page,
            page_size=page_size,
            total_results=total,
            total_pages=total_pages,
            results=summaries,
        )


    # -- public API: paper detail -------------------------------------------
    async def resolve_oa(
        self, pmcid: str
    ) -> tuple[dict[str, Any], list[DownloadLink]]:
        """Query the PMC OA service. Returns ``(record_attrs, download_links)``.

        Raises :class:`PaperNotFound` when the article is unknown to the OA service.
        """
        root = await self._oa_get_xml(pmcid)
        error_el = root.find(".//error")
        if error_el is not None and (error_el.text or "").strip():
            raise PaperNotFound(pmcid)
        record = root.find(".//record")
        if record is None:
            raise PaperNotFound(pmcid)
        record_attrs = dict(record.attrib)
        links: list[DownloadLink] = []
        for link in record.findall("link"):
            fmt = (link.attrib.get("format") or "").strip().lower()
            href = (link.attrib.get("href") or "").strip()
            if fmt in ("pdf", "tgz") and href:
                links.append(
                    DownloadLink(
                        format=fmt,
                        url=_to_https(href),  # type: ignore[arg-type]
                        updated=(link.attrib.get("updated") or "").strip(),
                    )
                )
        return record_attrs, links

    async def get_paper(self, pmcid: str) -> PaperDetail:
        """Return rich metadata + download links for a single PMCID."""
        pmcid = normalize_pmcid(pmcid)
        numeric = pmcid.replace("PMC", "", 1)
        numeric_ids, _ = await self._esearch_pmc(numeric, 0, 1)
        doc: dict[str, Any] = {}
        if numeric_ids:
            result = await self._esummary_pmc(numeric_ids[:1])
            uid = numeric_ids[0]
            doc = result.get(uid, {}) or {}
        summary = self._doc_to_summary(numeric_ids[0] if numeric_ids else "0", doc, {})

        snippet = summary.abstract_snippet
        if summary.pmid and not snippet:
            abstracts = await self._fetch_abstracts([summary.pmid])
            if abstracts.get(summary.pmid):
                snippet = _truncate(abstracts[summary.pmid])

        record_attrs, links = await self.resolve_oa(pmcid)

        return PaperDetail(
            pmcid=summary.pmcid or pmcid,
            pmid=summary.pmid,
            doi=summary.doi,
            title=summary.title,
            authors=summary.authors,
            journal=summary.journal,
            year=summary.year,
            license=record_attrs.get("license", ""),
            citation=record_attrs.get("citation", ""),
            retracted=(record_attrs.get("retracted", "no").lower() == "yes"),
            abstract_snippet=snippet,
            downloads=links,
        )


    # -- PDF download / cache ------------------------------------------------
    def _cache_path_for(self, pmcid: str) -> Path:
        return Path(self.settings.ncbi_cache_dir_resolved) / f"{pmcid}.pdf"

    async def _download_pdf(self, url: str, dest: Path) -> int:
        """Stream-download a PDF to ``dest`` and return the byte count."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        last_error = "no candidates tried"
        for candidate in candidate_download_urls(url):
            await self._limiter.acquire()
            try:
                async with self._client.stream("GET", candidate) as resp:
                    if resp.status_code == 404:
                        last_error = f"404 Not Found: {candidate}"
                        continue
                    resp.raise_for_status()
                    total = 0
                    with open(tmp, "wb") as fh:
                        async for chunk in resp.aiter_bytes():
                            fh.write(chunk)
                            total += len(chunk)
                tmp.replace(dest)
                return total
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue
        tmp.unlink(missing_ok=True)
        raise NcbiError(
            f"Failed to download PDF from {url}: {last_error}", status_code=502
        )

    async def _fetch_package_bytes(self, url: str) -> bytes:
        """Download a binary package, trying candidate mirror URLs in turn."""
        last_error = "no candidates tried"
        for candidate in candidate_download_urls(url):
            await self._limiter.acquire()
            try:
                resp = await self._client.get(candidate)
                if resp.status_code == 404:
                    last_error = f"404 Not Found: {candidate}"
                    continue
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPError as exc:
                last_error = str(exc)
                continue
        raise NcbiError(
            f"Failed to download package from {url}: {last_error}", status_code=502
        )

    async def _extract_pdf_from_tgz(self, url: str, dest: Path) -> int:
        """Download a ``.tar.gz`` OA package and extract the embedded PDF."""
        data = await self._fetch_package_bytes(url)
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                pdf_members = [
                    m
                    for m in tar.getmembers()
                    if m.isfile() and m.name.lower().endswith(".pdf")
                ]
                if not pdf_members:
                    raise NcbiError("OA package contained no PDF file.", status_code=422)
                member = max(pdf_members, key=lambda m: m.size)
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise NcbiError("Failed to read PDF from OA package.", status_code=502)
                pdf_bytes = extracted.read()
        except tarfile.TarError as exc:
            raise NcbiError(f"Failed to read OA package: {exc}", status_code=502) from exc

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(pdf_bytes)
        return len(pdf_bytes)

    async def fetch_paper(self, pmcid: str, *, force: bool = False) -> FetchResponse:
        """Download (or reuse the cached) PDF for ``pmcid``.

        Prefers a direct PDF link from the OA service; falls back to extracting
        the PDF from a ``.tar.gz`` package. When no PDF is available at all,
        returns a graceful ``unavailable`` response.
        """
        pmcid = normalize_pmcid(pmcid)
        cache_path = self._cache_path_for(pmcid)

        if cache_path.exists() and not force:
            return FetchResponse(
                pmcid=pmcid,
                status="cached",
                source_format="pdf",
                pdf_path=str(cache_path),
                filename=cache_path.name,
                size_bytes=cache_path.stat().st_size,
                message="PDF already present in cache.",
            )

        _, links = await self.resolve_oa(pmcid)
        pdf_links = [lk for lk in links if lk.format == "pdf"]
        tgz_links = [lk for lk in links if lk.format == "tgz"]

        if pdf_links:
            size = await self._download_pdf(str(pdf_links[0].url), cache_path)
            return FetchResponse(
                pmcid=pmcid,
                status="downloaded",
                source_format="pdf",
                pdf_path=str(cache_path),
                filename=cache_path.name,
                size_bytes=size,
                message="PDF downloaded from PMC OA service.",
            )

        if tgz_links:
            size = await self._extract_pdf_from_tgz(str(tgz_links[0].url), cache_path)
            return FetchResponse(
                pmcid=pmcid,
                status="extracted",
                source_format="tgz",
                pdf_path=str(cache_path),
                filename=cache_path.name,
                size_bytes=size,
                message="PDF extracted from PMC OA .tar.gz package.",
            )

        return FetchResponse(
            pmcid=pmcid,
            status="unavailable",
            source_format="none",
            pdf_path=None,
            filename=None,
            size_bytes=None,
            message="No PDF or downloadable package is available for this article.",
        )

