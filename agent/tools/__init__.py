"""Tools agents are allowed to call. Plain functions, testable without a model."""

from __future__ import annotations

from agent.tools.citation import CitationError, cite_source
from agent.tools.search import lexical_search, section_scan, synonym_search

__all__ = [
    "CitationError",
    "cite_source",
    "lexical_search",
    "section_scan",
    "synonym_search",
]
