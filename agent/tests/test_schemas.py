"""The schema is the system's integrity boundary, so test what it *rejects*."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.schemas import (
    Citation,
    Finding,
    FindingStatus,
    SearchEvidence,
    SearchStrategy,
    Severity,
    Verdict,
    VerificationResult,
)


def _citation() -> Citation:
    return Citation(page=3, paragraph=1, section_ref="9", quote="In no event shall either party")


def _evidence() -> SearchEvidence:
    return SearchEvidence(
        strategy=SearchStrategy.SEMANTIC, terms_searched=["cap"], blocks_examined=12
    )


def test_present_finding_requires_a_citation() -> None:
    with pytest.raises(ValidationError, match="requires at least one citation"):
        Finding(
            contract_id="NDA-8812",
            rule_id="NDA-006",
            clause_name="Cap on Damages",
            agent_name="liability_worker",
            status=FindingStatus.PRESENT,
            rationale="It is in there somewhere.",
        )


def test_missing_finding_cannot_carry_citations() -> None:
    """A quote from the document contradicts the claim that the clause is absent."""
    with pytest.raises(ValidationError, match="cannot carry citations"):
        Finding(
            contract_id="NDA-8812",
            rule_id="NDA-006",
            clause_name="Cap on Damages",
            agent_name="liability_worker",
            status=FindingStatus.MISSING,
            rationale="Not found.",
            citations=[_citation()],
            evidence=_evidence(),
        )


def test_missing_finding_requires_evidence() -> None:
    with pytest.raises(ValidationError, match="requires SearchEvidence"):
        Finding(
            contract_id="NDA-8812",
            rule_id="NDA-006",
            clause_name="Cap on Damages",
            agent_name="liability_worker",
            status=FindingStatus.MISSING,
            rationale="Not found.",
        )


def test_valid_missing_finding_is_accepted() -> None:
    finding = Finding(
        contract_id="NDA-8812",
        rule_id="NDA-006",
        clause_name="Cap on Damages",
        agent_name="liability_worker",
        status=FindingStatus.MISSING,
        rationale="Searched liability terms across all sections.",
        evidence=_evidence(),
        severity=Severity.CRITICAL,
    )
    assert finding.needs_verification is True


def test_unknown_fields_are_rejected() -> None:
    """extra='forbid' turns an invented field into an error, not a silent no-op."""
    with pytest.raises(ValidationError):
        Citation(page=1, paragraph=0, quote="text", hallucinated_field="oops")


def test_high_confidence_present_finding_skips_verification() -> None:
    finding = Finding(
        contract_id="NDA-8812",
        rule_id="NDA-006",
        clause_name="Cap on Damages",
        agent_name="liability_worker",
        status=FindingStatus.PRESENT,
        rationale="Located in General Provisions.",
        citations=[_citation()],
        confidence=0.95,
    )
    assert finding.needs_verification is False


def test_overturned_verdict_requires_counter_citations() -> None:
    with pytest.raises(ValidationError, match="requires counter_citations"):
        VerificationResult(
            finding_id="fnd_1",
            verdict=Verdict.OVERTURNED,
            reasoning="I found it, trust me.",
        )


def test_confirmed_verdict_needs_no_citations() -> None:
    result = VerificationResult(
        finding_id="fnd_1",
        verdict=Verdict.CONFIRMED,
        strategies_used=[SearchStrategy.SYNONYM, SearchStrategy.FULL_TEXT],
        reasoning="Searched exhaustively; genuinely absent.",
    )
    assert result.counter_citations == []
