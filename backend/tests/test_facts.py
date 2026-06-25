"""Tests for the heuristic facts extractor + registry extension point."""

from __future__ import annotations

import pytest

from app.schemas.ocr import Facts
from app.services import facts


# Canned OCR text mirroring the mock model output (so we know what to expect).
_TEXT = """# Mitochondrial Dynamics Regulate Longevity in Caenorhabditis elegans

Alice B. Researcher, Bob Q. Scientist, Carol Lee
Department of Biology, Example University

## Abstract

Mitochondrial dynamics balance fission and fusion. We show that reducing
fission extends lifespan. Our results demonstrate a 35% increase.

| Genotype | Mean lifespan (days) | n |
|---|---|---|
| wild-type (N2) | 18.2 | 120 |
| drp-1(ad817) | 24.6 | 118 |

## Results

We find that loss of DRP-1 increases lifespan. DAF-16 is required.

DOI: 10.1000/jexbio.2026.123456
PMCID: PMC1234567
"""


def test_extracts_title_authors_abstract() -> None:
    f = facts.extract_facts(_TEXT)
    assert f.title == "Mitochondrial Dynamics Regulate Longevity in Caenorhabditis elegans"
    assert f.authors == ["Alice B. Researcher", "Bob Q. Scientist", "Carol Lee"]
    assert f.abstract and "fission and fusion" in f.abstract


def test_extracts_key_findings() -> None:
    f = facts.extract_facts(_TEXT)
    assert any("We show" in kf for kf in f.key_findings)
    assert any("We find" in kf for kf in f.key_findings)


def test_extracts_doi_and_pmcid() -> None:
    f = facts.extract_facts(_TEXT)
    assert f.doi == "10.1000/jexbio.2026.123456"
    assert f.pmcid == "PMC1234567"


def test_extracts_entities() -> None:
    f = facts.extract_facts(_TEXT)
    # Acronyms / gene tokens should be captured (case-insensitive, deduped).
    lowered = [e.lower() for e in f.entities]
    assert "drp-1" in lowered
    assert "daf-16" in lowered


def test_extracts_table() -> None:
    f = facts.extract_facts(_TEXT)
    assert f.tables, "expected at least one markdown table"
    assert "Genotype" in f.tables[0]
    assert "|---|" in f.tables[0]


def test_empty_text_yields_empty_facts() -> None:
    f = facts.extract_facts("")
    assert f.extractor == "heuristic"
    assert f.title is None
    assert f.authors == []


def test_pmcid_argument_is_preserved() -> None:
    f = facts.extract_facts("Some text without a pmcid.", pmcid="PMC42")
    assert f.pmcid == "PMC42"


# --------------------------------------------------------------------------- #
# Extension point: register a custom extractor.
# --------------------------------------------------------------------------- #

def test_register_and_select_custom_extractor() -> None:
    @facts.register_fact_extractor("noop")
    def _noop(text: str, *, pmcid: str | None = None) -> Facts:
        return Facts(extractor="noop", title="CUSTOM")

    try:
        f = facts.extract_facts(_TEXT, extractor="noop")
        assert f.extractor == "noop"
        assert f.title == "CUSTOM"
    finally:
        facts._FACT_EXTRACTORS.pop("noop", None)


def test_heuristic_name_is_reserved() -> None:
    with pytest.raises(ValueError):
        facts.register_fact_extractor("heuristic")(lambda *a, **k: Facts())


def test_unknown_extractor_raises() -> None:
    with pytest.raises(KeyError):
        facts.extract_facts("x", extractor="does-not-exist")
