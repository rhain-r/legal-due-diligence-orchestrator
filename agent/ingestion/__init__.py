"""Deterministic document ingestion. No LLM calls live in this package."""

from __future__ import annotations

from agent.ingestion.chunker import chunk_blocks
from agent.ingestion.parser import parse_pages, parse_pdf

__all__ = ["chunk_blocks", "parse_pages", "parse_pdf"]
