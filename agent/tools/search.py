"""Retrieval strategies.

These exist so the verifier can search a document in a way that is *structurally*
different from how the worker read it. A worker reasons semantically over its
assigned chunks; the verifier runs lexical and synonym expansion over the entire
raw text. Two different mechanisms failing to find a clause is evidence. One
mechanism run twice is not.
"""

from __future__ import annotations

import re

from agent.schemas import ComplianceRule, TextBlock

#: Legal phrasings that carry clause meaning without using the clause's name.
#: A "cap on damages" is rarely labelled that way inside the operative sentence.
LEGAL_EXPANSIONS: dict[str, list[str]] = {
    "liability": [
        "aggregate liability",
        "limitation of liability",
        "shall not exceed",
        "in no event",
        "consequential damages",
        "cap on damages",
        "maximum liability",
    ],
    "termination": [
        "terminate",
        "termination for convenience",
        "notice of termination",
        "expiration of the term",
        "wind-down",
        "right to terminate",
    ],
    "jurisdiction": [
        "governing law",
        "governed by the laws",
        "venue",
        "exclusive jurisdiction",
        "submit to the jurisdiction",
        "choice of law",
    ],
    "confidentiality": [
        "confidential information",
        "non-disclosure",
        "proprietary information",
        "shall not disclose",
        "trade secret",
    ],
    "indemnity": [
        "indemnify",
        "hold harmless",
        "defend",
        "indemnification",
        "losses arising out of",
    ],
}


def _stem_terms(terms: list[str]) -> list[str]:
    """Crude suffix stripping. Good enough for legal boilerplate, no NLTK needed."""
    out: set[str] = set()
    for term in terms:
        t = term.lower().strip()
        if not t:
            continue
        out.add(t)
        for suffix in ("ies", "ing", "ed", "es", "s"):
            if len(t) > 5 and t.endswith(suffix):
                out.add(t[: -len(suffix)])
                break
    return sorted(out)


def lexical_search(blocks: list[TextBlock], terms: list[str]) -> list[TextBlock]:
    """Blocks containing any of `terms` (case-insensitive, lightly stemmed).

    Args:
        blocks: Document blocks to scan.
        terms: Words or phrases to look for.

    Returns:
        Matching blocks in document order.
    """
    needles = _stem_terms(terms)
    if not needles:
        return []
    hits: list[TextBlock] = []
    for block in blocks:
        lowered = block.text.lower()
        if any(n in lowered for n in needles):
            hits.append(block)
    return hits


def synonym_search(blocks: list[TextBlock], rule: ComplianceRule) -> list[TextBlock]:
    """Search using the rule's synonyms plus known legal phrasings for its domain.

    This is the verifier's primary tool against a MISSING claim: a clause that a
    worker missed is usually present under different words, not absent.
    """
    terms = list(rule.search_terms)
    terms.extend(LEGAL_EXPANSIONS.get(rule.domain.lower(), []))
    for key, expansions in LEGAL_EXPANSIONS.items():
        if key in rule.clause_name.lower():
            terms.extend(expansions)
    return lexical_search(blocks, terms)


def section_scan(blocks: list[TextBlock], heading_pattern: str) -> list[TextBlock]:
    """All blocks belonging to sections whose heading matches `heading_pattern`.

    Args:
        blocks: Document blocks to scan.
        heading_pattern: Regex tested against section refs and heading text.
    """
    try:
        pattern = re.compile(heading_pattern, re.I)
    except re.error as exc:
        raise ValueError(f"Invalid heading pattern {heading_pattern!r}: {exc}") from exc

    matching_sections = {
        b.section_ref
        for b in blocks
        if b.section_ref and (pattern.search(b.section_ref) or pattern.search(b.text[:120]))
    }
    if not matching_sections:
        return []
    return [b for b in blocks if b.section_ref in matching_sections]


def coverage_summary(blocks: list[TextBlock]) -> dict[str, int]:
    """Quick document statistics, recorded in traces for auditability."""
    return {
        "blocks": len(blocks),
        "pages": max((b.page for b in blocks), default=0),
        "sections": len({b.section_ref for b in blocks if b.section_ref}),
        "characters": sum(len(b.text) for b in blocks),
    }
