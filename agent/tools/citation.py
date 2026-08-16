"""The anti-hallucination gate.

Every citation in a report passes through `cite_source()`, which refuses to mint
one for text that is not in the document. An agent can hallucinate a quote; it
cannot hallucinate a Citation object, because this function checks the quote
against the source before returning.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from agent.schemas import Citation, TextBlock

logger = logging.getLogger(__name__)

#: Below this ratio a quote is treated as fabricated rather than merely noisy.
FUZZY_THRESHOLD = 0.90


class CitationError(ValueError):
    """Raised when a quote cannot be located in the cited source."""


def _normalize(text: str) -> str:
    """Collapse the differences that PDF extraction introduces but meaning does not."""
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def _best_window_ratio(needle: str, haystack: str) -> float:
    """Best similarity of `needle` against any same-length window of `haystack`."""
    if not needle or not haystack:
        return 0.0
    if len(needle) > len(haystack):
        return SequenceMatcher(None, needle, haystack).ratio()

    step = max(1, len(needle) // 4)
    best = 0.0
    for start in range(0, len(haystack) - len(needle) + 1, step):
        window = haystack[start : start + len(needle)]
        best = max(best, SequenceMatcher(None, needle, window).ratio())
        if best >= 0.99:
            break
    return best


def cite_source(block: TextBlock, quote: str) -> Citation:
    """Create a verified citation for `quote` within `block`.

    Use this whenever you want to report that the contract says something. Pass
    the exact wording you are relying on. If that wording does not appear in the
    block, this raises `CitationError` and the claim must be withdrawn.

    Args:
        block: The text block the quote is claimed to come from.
        quote: Verbatim contract language, ideally one sentence.

    Returns:
        A Citation carrying the page, paragraph, and section of the quote.

    Raises:
        CitationError: The quote is absent from the block.
    """
    if not quote or not quote.strip():
        raise CitationError("Empty quote: a citation must quote actual contract text.")

    needle = _normalize(quote)
    haystack = _normalize(block.text)

    exact = needle in haystack
    fuzzy = False

    if not exact:
        ratio = _best_window_ratio(needle, haystack)
        if ratio < FUZZY_THRESHOLD:
            raise CitationError(
                f"Quote not found in {block.block_id} ({block.locator}). "
                f"Best similarity {ratio:.2f} < {FUZZY_THRESHOLD}. "
                "Do not cite text that is not in the document — if you cannot quote "
                "it, you cannot claim it."
            )
        fuzzy = True
        logger.warning(
            "Fuzzy citation accepted in %s (ratio %.2f): %r", block.block_id, ratio, quote[:80]
        )

    return Citation(
        page=block.page,
        paragraph=block.paragraph,
        section_ref=block.section_ref,
        quote=quote.strip()[:500],
        block_id=block.block_id,
        fuzzy_match=fuzzy,
    )


def cite_from_blocks(blocks: list[TextBlock], quote: str) -> Citation:
    """Locate `quote` across many blocks and cite the one that contains it.

    Convenience for agents that know what the document said but not which block
    it was in. Raises CitationError if no block contains the quote.
    """
    for block in blocks:
        try:
            return cite_source(block, quote)
        except CitationError:
            continue

    # Report how close the best block came. The difference between 0.89 (drifted
    # quote, worth loosening the threshold) and 0.20 (fabricated) is the first
    # thing anyone debugging the citation gate needs, and it is invisible from
    # "not found" alone.
    needle = _normalize(quote)
    best = max((_best_window_ratio(needle, _normalize(b.text)) for b in blocks), default=0.0)
    raise CitationError(
        f"Quote not found in any of {len(blocks)} blocks (best similarity "
        f"{best:.2f}, threshold {FUZZY_THRESHOLD}): {quote[:120]!r}"
    )
