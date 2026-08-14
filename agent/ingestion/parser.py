"""PDF -> anchored text blocks.

Everything here is pure and deterministic so it can be unit-tested without a
model or an API key. This matters more than it looks: a citation is only as
trustworthy as the page number that survived parsing. Flatten a contract into
one undifferentiated blob and every downstream citation becomes a plausible guess.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from agent.schemas import TextBlock

# "7.1 Limitation of Liability", "ARTICLE IV — Term", "Section 12. Notices"
_SECTION_PATTERNS = [
    re.compile(r"^\s*(?P<ref>\d+(?:\.\d+){0,3})\s*[.\-–—:)]?\s+(?P<title>[A-Z][^\n]{2,50})$"),
    re.compile(
        r"^\s*ARTICLE\s+(?P<ref>[IVXLCDM]+|\d+)\s*[.\-–—:]?\s*(?P<title>[^\n]{0,80})$", re.I
    ),
    re.compile(r"^\s*SECTION\s+(?P<ref>\d+(?:\.\d+)*)\s*[.\-–—:]?\s*(?P<title>[^\n]{0,80})$", re.I),
]

#: Headings are short. Prose that happens to start with a number is not.
#: Without this bound, "14 March 2025 (the Effective Date) by and between..."
#: parses as section 14 and poisons every citation that follows it.
_MAX_HEADING_CHARS = 60

# A line that is only a page number, or "Page 4 of 27".
_PAGE_NUMBER_ONLY = re.compile(r"^\s*(?:page\s+)?\d+\s*(?:of\s+\d+)?\s*$", re.I)

# Word split across a line break: "indemnifi-\ncation" -> "indemnification"
_HYPHEN_WRAP = re.compile(r"(\w)-\s*\n\s*(\w)")


def _detect_boilerplate(pages: list[str], min_pages: int = 3) -> set[str]:
    """Find header/footer lines repeated across most pages.

    Real contracts repeat a firm name or matter number on every page. Left in,
    those lines pollute chunks and can be mistaken for clause text.
    """
    if len(pages) < min_pages:
        return set()

    counts: Counter[str] = Counter()
    for page in pages:
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        # Only the top and bottom of a page can be a running header/footer.
        for line in set(lines[:2] + lines[-2:]):
            if 3 < len(line) < 120:
                counts[line] += 1

    threshold = max(min_pages, int(len(pages) * 0.6))
    return {line for line, n in counts.items() if n >= threshold}


def _clean_page(raw: str, boilerplate: set[str]) -> str:
    text = _HYPHEN_WRAP.sub(r"\1\2", raw)
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in boilerplate:
            continue
        if _PAGE_NUMBER_ONLY.match(stripped):
            continue
        kept.append(line)
    return "\n".join(kept)


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_CHARS:
        return False
    if any(p.match(stripped) for p in _SECTION_PATTERNS):
        return True
    # Short all-caps lines are headings ("RECITALS", "NOW THEREFORE").
    letters = [c for c in stripped if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(stripped) < 50


def _reflow_lines(lines: list[str]) -> list[str]:
    """Rebuild paragraphs from a page that extracted as bare lines.

    Many PDFs carry no blank lines through text extraction, so splitting on them
    yields one block per *line* — which severs sentences and makes a clause look
    absent to both halves. Join lines until one ends in sentence-final
    punctuation, breaking at anything that looks like a heading.
    """
    paragraphs: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            paragraphs.append(" ".join(buffer))
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if _looks_like_heading(stripped):
            flush()
            paragraphs.append(stripped)
            continue
        buffer.append(stripped)
        if stripped.endswith((".", ";", ":", "?", "!")):
            flush()

    flush()
    return paragraphs


def _split_paragraphs(page_text: str) -> list[str]:
    """Split into paragraphs, reflowing when blank lines did not survive extraction."""
    parts = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
    if len(parts) <= 1 and page_text.count("\n") > 4:
        parts = _reflow_lines(page_text.splitlines())
    return [re.sub(r"[ \t]+", " ", p.replace("\n", " ")).strip() for p in parts]


def _match_section(paragraph: str) -> str | None:
    head = paragraph.splitlines()[0].strip() if paragraph else ""
    if not head or len(head) > _MAX_HEADING_CHARS:
        return None
    for pattern in _SECTION_PATTERNS:
        m = pattern.match(head)
        if m:
            return m.group("ref").strip()
    return None


def parse_pages(pages: list[str], *, drop_boilerplate: bool = True) -> list[TextBlock]:
    """Turn raw per-page text into anchored blocks.

    Split out from `parse_pdf` so tests can exercise normalization without
    generating a PDF.
    """
    boilerplate = _detect_boilerplate(pages) if drop_boilerplate else set()
    blocks: list[TextBlock] = []
    current_section: str | None = None
    running_chars = 0

    for page_index, raw in enumerate(pages, start=1):
        cleaned = _clean_page(raw, boilerplate)
        for para_index, paragraph in enumerate(_split_paragraphs(cleaned)):
            section = _match_section(paragraph)
            if section:
                current_section = section
            blocks.append(
                TextBlock(
                    block_id=f"b{page_index:03d}_{para_index:03d}",
                    page=page_index,
                    paragraph=para_index,
                    text=paragraph,
                    section_ref=current_section,
                    char_start=running_chars,
                )
            )
            running_chars += len(paragraph) + 2

    return blocks


def parse_pdf(path: str | Path, *, drop_boilerplate: bool = True) -> list[TextBlock]:
    """Extract anchored text blocks from a PDF.

    Raises FileNotFoundError if missing, or ValueError if the PDF yields no text
    (almost always a scanned document that needs OCR first — worth failing loudly
    rather than silently auditing an empty string).
    """
    from pypdf import PdfReader  # imported lazily: keeps schema-only imports cheap

    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"Contract not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    pages = [(page.extract_text() or "") for page in reader.pages]

    blocks = parse_pages(pages, drop_boilerplate=drop_boilerplate)
    if not blocks:
        raise ValueError(
            f"No extractable text in {pdf_path.name}. If this is a scanned contract, "
            "run OCR before auditing it — an empty parse would otherwise report every "
            "clause as missing."
        )
    return blocks


def page_count(blocks: list[TextBlock]) -> int:
    return max((b.page for b in blocks), default=0)
