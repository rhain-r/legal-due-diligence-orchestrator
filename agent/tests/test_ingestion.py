"""Parsing and chunking. Deterministic, so these tests are exact, not approximate."""

from __future__ import annotations

from itertools import pairwise

import pytest

from agent.ingestion.chunker import chunk_blocks, select_chunks_for_terms
from agent.ingestion.parser import page_count, parse_pages, parse_pdf
from agent.schemas import TextBlock
from agent.tests.conftest import CONTRACT_PAGES


def test_text_anchors_to_the_correct_page(blocks: list[TextBlock]) -> None:
    """The whole citation story rests on this round-trip."""
    hits = [b for b in blocks if "aggregate obligation" in b.text]
    assert len(hits) == 1
    assert hits[0].page == 3


def test_hyphenated_line_wrap_is_rejoined(blocks: list[TextBlock]) -> None:
    """'Indemnifi-\\ncation' must not survive as two fragments."""
    full_text = " ".join(b.text for b in blocks)
    assert "Indemnifi- cation" not in full_text
    assert "Indemnification" in full_text


def test_repeated_page_headers_are_dropped(blocks: list[TextBlock]) -> None:
    """The matter header appears on all three pages and is not clause text."""
    assert not any("Matter 8812" in b.text for b in blocks)


def test_page_number_only_lines_are_dropped(blocks: list[TextBlock]) -> None:
    assert not any(b.text.strip().isdigit() for b in blocks)


def test_section_refs_are_detected_and_carried_forward(blocks: list[TextBlock]) -> None:
    cap = next(b for b in blocks if "aggregate obligation" in b.text)
    assert cap.section_ref == "9"

    definition = next(b for b in blocks if "Confidential Information" in b.text)
    assert definition.section_ref == "1"


def test_prose_beginning_with_a_number_is_not_a_section() -> None:
    """Regression: a date opening a sentence used to parse as a section heading.

    Once that happens every later block inherits the bogus ref and citations
    point at a section that does not exist.
    """
    parsed = parse_pages(
        [
            "1. Definitions\n"
            "\n"
            "14 March 2025 (the \"Effective Date\") by and between Vertex Analytics "
            "Ltd., a company incorporated in England and Wales.\n"
        ]
    )
    assert {b.section_ref for b in parsed} == {"1"}


def test_locator_is_human_readable(blocks: list[TextBlock]) -> None:
    cap = next(b for b in blocks if "aggregate obligation" in b.text)
    assert cap.locator.startswith("§9 (p.3")


def test_page_count(blocks: list[TextBlock]) -> None:
    assert page_count(blocks) == 3


def test_empty_document_yields_no_blocks() -> None:
    assert parse_pages(["", "   ", "\n\n"]) == []


def test_parse_pdf_reports_a_missing_file() -> None:
    with pytest.raises(FileNotFoundError, match="Contract not found"):
        parse_pdf("does-not-exist.pdf")


# --- Chunking ----------------------------------------------------------------


def test_chunks_never_split_a_paragraph(blocks: list[TextBlock]) -> None:
    chunks = chunk_blocks(blocks, target_chars=200, overlap_blocks=0)
    rejoined = [b.text for c in chunks for b in c.blocks]
    for block in blocks:
        assert block.text in rejoined


def test_chunk_overlap_repeats_the_boundary_block(blocks: list[TextBlock]) -> None:
    """A clause straddling a boundary must be fully visible to at least one worker."""
    chunks = chunk_blocks(blocks, target_chars=200, overlap_blocks=1)
    assert len(chunks) > 1
    for earlier, later in pairwise(chunks):
        assert earlier.blocks[-1].block_id == later.blocks[0].block_id


def test_chunk_reports_its_page_range(blocks: list[TextBlock]) -> None:
    chunks = chunk_blocks(blocks, target_chars=100_000)
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 3


def test_empty_input_produces_no_chunks() -> None:
    assert chunk_blocks([]) == []


def test_negative_overlap_is_rejected(blocks: list[TextBlock]) -> None:
    with pytest.raises(ValueError, match="overlap_blocks"):
        chunk_blocks(blocks, overlap_blocks=-1)


def test_chunk_selection_falls_back_to_everything(blocks: list[TextBlock]) -> None:
    """A keyword miss is not evidence of absence, so never hand a worker nothing."""
    chunks = chunk_blocks(blocks, target_chars=200)
    selected = select_chunks_for_terms(chunks, ["kryptonite indemnity waiver"])
    assert selected == chunks


def test_chunk_selection_narrows_on_a_hit(blocks: list[TextBlock]) -> None:
    chunks = chunk_blocks(blocks, target_chars=200)
    selected = select_chunks_for_terms(chunks, ["aggregate obligation"])
    assert 0 < len(selected) < len(chunks)


def test_render_includes_locators(blocks: list[TextBlock]) -> None:
    chunk = chunk_blocks(blocks, target_chars=100_000)[0]
    rendered = chunk.render()
    assert "p.3" in rendered
    assert chunk.blocks[0].block_id in rendered


def test_real_pdf_round_trip(tmp_path) -> None:
    """Optional end-to-end check against an actual PDF, if reportlab is installed."""
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")

    path = tmp_path / "sample.pdf"
    pdf = reportlab.Canvas(str(path))
    for page in CONTRACT_PAGES:
        y = 800
        for line in page.splitlines():
            pdf.drawString(60, y, line[:95])
            y -= 14
        pdf.showPage()
    pdf.save()

    parsed = parse_pdf(path)
    assert page_count(parsed) == 3
    assert any("aggregate obligation" in b.text for b in parsed)
