"""Unit tests for service helpers (rate limiter, normalization, parsing)."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.services.ncbi import (
    NcbiService,
    RateLimiter,
    _extract_year,
    _to_https,
    _truncate,
    candidate_download_urls,
    normalize_pmcid,
)
from app.services.ncbi import NcbiError


# --------------------------------------------------------------------------- #
# normalize_pmcid
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("PMC5334499", "PMC5334499"),
        ("5334499", "PMC5334499"),
        ("pmc5334499", "PMC5334499"),
        ("  PMC123  ", "PMC123"),
    ],
)
def test_normalize_pmcid(raw, expected):
    assert normalize_pmcid(raw) == expected


def test_normalize_pmcid_invalid():
    with pytest.raises(NcbiError) as exc_info:
        normalize_pmcid("not-a-pmc")
    assert exc_info.value.status_code == 400


# --------------------------------------------------------------------------- #
# _to_https / candidate_download_urls
# --------------------------------------------------------------------------- #


def test_to_https_converts_ftp():
    assert _to_https(
        "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/x.pdf"
    ) == "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/x.pdf"


def test_to_https_passes_through_https():
    url = "https://example.com/a.pdf"
    assert _to_https(url) == url


def test_candidate_urls_converts_ftp_and_adds_deprecated_fallback():
    ftp = "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/0a/fa/PMC1.tar.gz"
    cands = candidate_download_urls(ftp)
    assert cands[0] == "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_package/0a/fa/PMC1.tar.gz"
    assert cands[1] == (
        "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_package/0a/fa/PMC1.tar.gz"
    )


def test_candidate_urls_no_fallback_for_non_pmc_paths():
    url = "https://example.com/some/file.pdf"
    assert candidate_download_urls(url) == [url]


def test_candidate_urls_idempotent_when_already_deprecated():
    url = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/deprecated/oa_pdf/x.pdf"
    assert candidate_download_urls(url) == [url]


# --------------------------------------------------------------------------- #
# _extract_year / _truncate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "pubdate, year",
    [
        ("2017 Feb 28", "2017"),
        ("2009 Dec", "2009"),
        ("2020", "2020"),
        ("no date here", ""),
    ],
)
def test_extract_year(pubdate, year):
    assert _extract_year(pubdate) == year


def test_truncate_short_text_unchanged():
    assert _truncate("short text") == "short text"


def test_truncate_long_text_ellipsized():
    out = _truncate("word " * 200, limit=40)
    assert len(out) <= 41  # 40 + ellipsis
    assert out.endswith("…")


# --------------------------------------------------------------------------- #
# RateLimiter (run via asyncio.run so no pytest-asyncio is needed)
# --------------------------------------------------------------------------- #


def test_rate_limiter_enforces_minimum_spacing():
    rate = 100  # 100 req/s -> 0.01s spacing
    limiter = RateLimiter(rate_per_second=rate)

    async def go():
        for _ in range(5):
            await limiter.acquire()

    start = time.perf_counter()
    asyncio.run(go())
    elapsed = time.perf_counter() - start
    # 5 acquisitions => 4 intervals of >= 1/100 s.
    assert elapsed >= (5 - 1) / rate - 0.01


def test_rate_limiter_zero_rate_no_delay():
    limiter = RateLimiter(rate_per_second=0)

    async def go():
        for _ in range(10):
            await limiter.acquire()

    start = time.perf_counter()
    asyncio.run(go())
    assert time.perf_counter() - start < 0.05


# --------------------------------------------------------------------------- #
# Abstract parsing
# --------------------------------------------------------------------------- #


def test_parse_pubmed_abstracts():
    xml = """<?xml version="1.0"?>
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID Version="1">111</PMID>
          <Article>
            <Abstract>
              <AbstractText Label="BACKGROUND">First part.</AbstractText>
              <AbstractText Label="RESULTS">Second part.</AbstractText>
            </Abstract>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>"""
    out = NcbiService._parse_pubmed_abstracts(xml)
    assert out["111"] == "BACKGROUND: First part. RESULTS: Second part."


def test_parse_pubmed_abstracts_empty():
    assert NcbiService._parse_pubmed_abstracts("not xml") == {}
