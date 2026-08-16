"""Scoring, report assembly, SOP loading, and JSON round-trip."""

from __future__ import annotations

import pytest

from agent.reporter import (
    build_report,
    compute_risk_score,
    load_report,
    render_markdown,
    write_json,
)
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
from agent.sop import load_sop


def _finding(status: FindingStatus, severity: Severity, rule_id: str = "R1") -> Finding:
    kwargs = {
        "contract_id": "NDA-8812",
        "rule_id": rule_id,
        "clause_name": "Cap on Damages",
        "agent_name": "liability_worker",
        "status": status,
        "severity": severity,
        "rationale": "reasoning",
    }
    if status is FindingStatus.MISSING:
        kwargs["evidence"] = SearchEvidence(
            strategy=SearchStrategy.SEMANTIC, blocks_examined=5
        )
    else:
        kwargs["citations"] = [Citation(page=3, paragraph=1, quote="In no event shall")]
    return Finding(**kwargs)


# --- Scoring -----------------------------------------------------------------


def test_clean_contract_scores_zero() -> None:
    findings = [_finding(FindingStatus.PRESENT, Severity.CRITICAL)]
    assert compute_risk_score(findings) == 0.0


def test_all_critical_gaps_score_one_hundred() -> None:
    findings = [_finding(FindingStatus.MISSING, Severity.CRITICAL, f"R{i}") for i in range(3)]
    assert compute_risk_score(findings) == 100.0


def test_score_is_normalised_across_rule_set_sizes() -> None:
    """Two contracts with the same proportion of gaps score the same."""
    small = [
        _finding(FindingStatus.MISSING, Severity.HIGH, "R1"),
        _finding(FindingStatus.PRESENT, Severity.HIGH, "R2"),
    ]
    large = [
        *[_finding(FindingStatus.MISSING, Severity.HIGH, f"M{i}") for i in range(5)],
        *[_finding(FindingStatus.PRESENT, Severity.HIGH, f"P{i}") for i in range(5)],
    ]
    assert compute_risk_score(small) == compute_risk_score(large) == 50.0


def test_ambiguous_scores_less_than_missing() -> None:
    ambiguous = [_finding(FindingStatus.AMBIGUOUS, Severity.HIGH)]
    missing = [_finding(FindingStatus.MISSING, Severity.HIGH)]
    assert 0 < compute_risk_score(ambiguous) < compute_risk_score(missing)


def test_empty_findings_score_zero() -> None:
    assert compute_risk_score([]) == 0.0


# --- Report ------------------------------------------------------------------


def test_report_round_trips_through_strict_json(tmp_path) -> None:
    report = build_report(
        contract_id="NDA-8812",
        source_file="nda.pdf",
        audit_id="aud_test123",
        rules_evaluated=2,
        findings=[
            _finding(FindingStatus.MISSING, Severity.CRITICAL, "NDA-006"),
            _finding(FindingStatus.PRESENT, Severity.HIGH, "NDA-005"),
        ],
        verifications=[],
        overturned=[],
        page_count=3,
    )
    path = write_json(report, tmp_path)
    restored = load_report(path)

    assert restored.audit_id == report.audit_id
    assert restored.risk_score == report.risk_score
    assert len(restored.confirmed_gaps) == 1


def test_overturned_findings_are_retained_in_the_audit_trail() -> None:
    overturned = _finding(FindingStatus.MISSING, Severity.CRITICAL, "NDA-006")
    report = build_report(
        contract_id="NDA-8812",
        source_file="nda.pdf",
        audit_id="aud_test123",
        rules_evaluated=1,
        findings=[_finding(FindingStatus.PRESENT, Severity.CRITICAL, "NDA-006")],
        verifications=[],
        overturned=[overturned],
    )
    assert report.verifier_lift == 1
    assert "overturned" in render_markdown(report).lower()


def test_escalated_findings_are_listed_as_unresolved() -> None:
    """Derived from verdicts, not from matching prose in the rationale."""
    finding = _finding(FindingStatus.MISSING, Severity.HIGH, "NDA-004")
    report = build_report(
        contract_id="NDA-8812",
        source_file="nda.pdf",
        audit_id="aud_1",
        rules_evaluated=1,
        findings=[finding],
        verifications=[
            VerificationResult(
                finding_id=finding.finding_id,
                verdict=Verdict.NEEDS_HUMAN,
                reasoning="Arguably on point; a lawyer must decide.",
            )
        ],
        overturned=[],
    )
    assert report.unresolved == ["NDA-004"]


def test_confirmed_findings_are_not_unresolved() -> None:
    finding = _finding(FindingStatus.MISSING, Severity.HIGH, "NDA-006")
    report = build_report(
        contract_id="NDA-8812",
        source_file="nda.pdf",
        audit_id="aud_1",
        rules_evaluated=1,
        findings=[finding],
        verifications=[
            VerificationResult(
                finding_id=finding.finding_id,
                verdict=Verdict.CONFIRMED,
                reasoning="Searched exhaustively; genuinely absent.",
            )
        ],
        overturned=[],
    )
    assert report.unresolved == []


def test_markdown_reports_a_clean_contract() -> None:
    report = build_report(
        contract_id="NDA-1",
        source_file="nda.pdf",
        audit_id="aud_1",
        rules_evaluated=1,
        findings=[_finding(FindingStatus.PRESENT, Severity.LOW)],
        verifications=[],
        overturned=[],
    )
    assert "Every rule in the SOP was satisfied" in render_markdown(report)


# --- SOP ---------------------------------------------------------------------


def test_bundled_nda_sop_loads_and_validates() -> None:
    sop = load_sop("nda_sop.yaml")
    assert len(sop.rules) >= 8
    assert "liability" in sop.domains
    assert all(rule.description for rule in sop.rules)


def test_sop_rules_have_synonyms_for_the_verifier() -> None:
    """Synonyms are what let the verifier find a clause the worker missed."""
    sop = load_sop("nda_sop.yaml")
    assert all(rule.synonyms for rule in sop.rules)


def test_missing_sop_lists_available_files() -> None:
    with pytest.raises(FileNotFoundError, match="Available in agent/rules/"):
        load_sop("no_such_sop.yaml")


def test_search_terms_are_deduplicated() -> None:
    sop = load_sop("nda_sop.yaml")
    rule = sop.rules[0]
    assert len(rule.search_terms) == len(set(rule.search_terms))
