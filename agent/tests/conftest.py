"""Shared fixtures.

The contract fixture is deliberately adversarial: the cap on damages is present
but never uses the words "cap" or "damages" in its operative sentence. A naive
keyword reviewer reports it missing. That is the case the whole system exists for.
"""

from __future__ import annotations

import json

import pytest

from agent.config import Settings
from agent.ingestion.parser import parse_pages
from agent.schemas import ComplianceRule, Severity, TextBlock

CONTRACT_PAGES = [
    # Page 1
    "MUTUAL NON-DISCLOSURE AGREEMENT\n"
    "Acme Holdings LLP — Matter 8812\n"
    "\n"
    "1. Definitions\n"
    "\n"
    '"Confidential Information" means any information disclosed by either party, '
    "whether in writing, orally, or by inspection of tangible objects.\n"
    "\n"
    "2. Obligations\n"
    "\n"
    "The Receiving Party shall not disclose Confidential Information to any third "
    "party without prior written consent.\n"
    "\n"
    "1",
    # Page 2 — note the hyphenated line wrap on "indemnification"
    "Acme Holdings LLP — Matter 8812\n"
    "\n"
    "3. Term\n"
    "\n"
    "This Agreement shall commence on the Effective Date and continue for three (3) "
    "years, provided that the confidentiality obligations shall survive for five (5) "
    "years following expiration.\n"
    "\n"
    "4. Indemnifi-\n"
    "cation\n"
    "\n"
    "Each party shall indemnify the other against losses arising out of its breach.\n"
    "\n"
    "2",
    # Page 3 — the cap on damages, buried in General Provisions and oddly worded
    "Acme Holdings LLP — Matter 8812\n"
    "\n"
    "9. General Provisions\n"
    "\n"
    "In no event shall either party's aggregate obligation arising hereunder exceed "
    "the fees paid in the preceding twelve (12) months.\n"
    "\n"
    "Neither party shall be responsible for indirect or consequential losses "
    "howsoever arising.\n"
    "\n"
    "3",
]


@pytest.fixture
def blocks() -> list[TextBlock]:
    return parse_pages(CONTRACT_PAGES)


@pytest.fixture
def liability_rule() -> ComplianceRule:
    return ComplianceRule(
        rule_id="NDA-006",
        clause_name="Cap on Damages",
        domain="liability",
        description="Liability must be limited by an aggregate cap.",
        synonyms=["limitation of liability", "shall not exceed", "in no event"],
        severity=Severity.CRITICAL,
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        anthropic_api_key="test-key",
        google_api_key="test-key",
        max_verification_strategies=3,
    )


def canned(payload: dict) -> str:
    """Serialise a dict the way a model would return it."""
    return json.dumps(payload)
