"""The citation gate and the retrieval strategies."""

from __future__ import annotations

import pytest

from agent.schemas import ComplianceRule, TextBlock
from agent.tools.citation import CitationError, cite_from_blocks, cite_source
from agent.tools.search import coverage_summary, lexical_search, section_scan, synonym_search


def _cap_block(blocks: list[TextBlock]) -> TextBlock:
    return next(b for b in blocks if "aggregate obligation" in b.text)


def test_fabricated_quote_is_rejected(blocks: list[TextBlock]) -> None:
    """The single most important test in the repo."""
    with pytest.raises(CitationError, match="Quote not found"):
        cite_source(_cap_block(blocks), "Liability is capped at one million dollars.")


def test_empty_quote_is_rejected(blocks: list[TextBlock]) -> None:
    with pytest.raises(CitationError, match="Empty quote"):
        cite_source(_cap_block(blocks), "   ")


def test_exact_quote_produces_an_anchored_citation(blocks: list[TextBlock]) -> None:
    block = _cap_block(blocks)
    citation = cite_source(block, "aggregate obligation arising hereunder")
    assert citation.page == 3
    assert citation.section_ref == "9"
    assert citation.fuzzy_match is False


def test_whitespace_and_smart_quote_drift_is_tolerated(blocks: list[TextBlock]) -> None:
    """PDF extraction introduces noise that does not change meaning."""
    block = _cap_block(blocks)
    citation = cite_source(block, "aggregate   obligation\narising  hereunder")
    assert citation.page == 3


def test_near_miss_below_threshold_still_raises(blocks: list[TextBlock]) -> None:
    """Fuzzy matching must not become a licence to paraphrase."""
    with pytest.raises(CitationError):
        cite_source(_cap_block(blocks), "the total liability of the parties is limited to nothing")


def test_cite_from_blocks_finds_the_right_block(blocks: list[TextBlock]) -> None:
    citation = cite_from_blocks(blocks, "shall survive for five (5) years")
    assert citation.page == 2


def test_cite_from_blocks_raises_when_absent(blocks: list[TextBlock]) -> None:
    with pytest.raises(CitationError, match="not found in any"):
        cite_from_blocks(blocks, "arbitration shall be conducted in Singapore")


def test_citation_str_is_readable(blocks: list[TextBlock]) -> None:
    citation = cite_source(_cap_block(blocks), "aggregate obligation")
    assert str(citation) == "§9, p.3 ¶1"


# --- Search ------------------------------------------------------------------


def test_lexical_search_is_case_insensitive(blocks: list[TextBlock]) -> None:
    assert lexical_search(blocks, ["CONFIDENTIAL INFORMATION"])


def test_lexical_search_with_no_terms_returns_nothing(blocks: list[TextBlock]) -> None:
    assert lexical_search(blocks, []) == []


def test_synonym_search_finds_a_clause_that_shares_no_keywords(
    blocks: list[TextBlock], liability_rule: ComplianceRule
) -> None:
    """The verifier's core capability, tested directly.

    The cap on damages never says "cap" or "damages". A worker searching the
    clause name finds nothing; synonym expansion finds it via "in no event".
    """
    assert lexical_search(blocks, ["cap on damages"]) == []

    hits = synonym_search(blocks, liability_rule)
    assert any("aggregate obligation" in b.text for b in hits)


def test_section_scan_finds_catchall_sections(blocks: list[TextBlock]) -> None:
    hits = section_scan(blocks, r"general|miscellaneous")
    assert any("aggregate obligation" in b.text for b in hits)


def test_section_scan_rejects_a_bad_pattern(blocks: list[TextBlock]) -> None:
    with pytest.raises(ValueError, match="Invalid heading pattern"):
        section_scan(blocks, "[unclosed")


def test_coverage_summary(blocks: list[TextBlock]) -> None:
    stats = coverage_summary(blocks)
    assert stats["pages"] == 3
    assert stats["blocks"] > 0
    assert stats["sections"] >= 4
