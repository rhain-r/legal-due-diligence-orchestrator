"""Worker and verifier behaviour, driven by canned model responses.

No network, no API keys, no cost. Real API calls in a unit suite make it slow,
flaky, and expensive — none of which a test suite can afford to be.
"""

from __future__ import annotations

import pytest

from agent.config import Settings
from agent.ingestion.chunker import chunk_blocks
from agent.llm import ModelError, StubClient, complete_structured, extract_json
from agent.schemas import (
    ComplianceRule,
    Finding,
    FindingStatus,
    SearchEvidence,
    SearchStrategy,
    Severity,
    TextBlock,
    Verdict,
)
from agent.tests.conftest import canned
from agent.verifier import VerifierAgent
from agent.workers import ClauseWorker, WorkerResponse

CAP_QUOTE = "aggregate obligation arising hereunder exceed the fees paid"


def _missing_finding(rule: ComplianceRule) -> Finding:
    return Finding(
        contract_id="NDA-8812",
        rule_id=rule.rule_id,
        clause_name=rule.clause_name,
        agent_name="liability_worker",
        status=FindingStatus.MISSING,
        severity=Severity.CRITICAL,
        rationale="No clause capping damages was found.",
        evidence=SearchEvidence(
            strategy=SearchStrategy.SEMANTIC,
            terms_searched=["cap on damages", "limitation of liability"],
            blocks_examined=9,
        ),
        confidence=0.8,
    )


# --- Structured output -------------------------------------------------------


def test_extract_json_handles_a_code_fence() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_extract_json_handles_surrounding_prose() -> None:
    assert extract_json('Sure! {"a": 1} Hope that helps.') == '{"a": 1}'


async def test_structured_output_retries_on_invalid_json() -> None:
    """The validation error is fed back, turning the schema into a correction signal."""
    client = StubClient(
        [
            "not json at all",
            canned({"status": "missing", "rationale": "absent", "confidence": 0.9}),
        ]
    )
    result = await complete_structured(client, "sys", "prompt", WorkerResponse)
    assert result.status is FindingStatus.MISSING
    assert len(client.calls) == 2
    assert "failed validation" in client.calls[1][1]


async def test_structured_output_raises_after_exhausting_retries() -> None:
    client = StubClient(["garbage", "still garbage", "nope"])
    with pytest.raises(ModelError, match="could not produce valid"):
        await complete_structured(client, "sys", "prompt", WorkerResponse)


# --- Workers -----------------------------------------------------------------


async def test_worker_produces_a_cited_finding(
    blocks: list[TextBlock], liability_rule: ComplianceRule
) -> None:
    client = StubClient(
        [
            canned(
                {
                    "status": "present",
                    "rationale": "A cap is expressed in General Provisions.",
                    "quotes": [CAP_QUOTE],
                    "confidence": 0.92,
                }
            )
        ]
    )
    worker = ClauseWorker(liability_rule, client)
    finding = await worker.run("NDA-8812", chunk_blocks(blocks))

    assert finding.status is FindingStatus.PRESENT
    assert finding.citations[0].page == 3
    assert finding.needs_verification is False


async def test_worker_downgrades_an_unverifiable_claim(
    blocks: list[TextBlock], liability_rule: ComplianceRule
) -> None:
    """A model asserting a clause it cannot quote must not be reported as found."""
    client = StubClient(
        [
            canned(
                {
                    "status": "present",
                    "rationale": "There is definitely a cap.",
                    "quotes": ["Liability is capped at USD 1,000,000."],
                    "confidence": 0.95,
                }
            )
        ]
    )
    worker = ClauseWorker(liability_rule, client)
    finding = await worker.run("NDA-8812", chunk_blocks(blocks))

    assert finding.status is FindingStatus.MISSING
    assert finding.citations == []
    assert finding.evidence is not None
    assert finding.needs_verification is True


async def test_worker_missing_finding_carries_evidence(
    blocks: list[TextBlock], liability_rule: ComplianceRule
) -> None:
    client = StubClient(
        [
            canned(
                {
                    "status": "missing",
                    "rationale": "No cap located.",
                    "terms_searched": ["cap on damages"],
                    "sections_scanned": ["1", "2"],
                    "confidence": 0.7,
                }
            )
        ]
    )
    finding = await ClauseWorker(liability_rule, client).run("NDA-8812", chunk_blocks(blocks))
    assert finding.evidence is not None
    assert finding.evidence.terms_searched == ["cap on damages"]


# --- Verifier: the thesis of the project -------------------------------------


async def test_verifier_overturns_a_false_absence_claim(
    blocks: list[TextBlock], liability_rule: ComplianceRule, settings: Settings
) -> None:
    """The clause IS present, phrased so oddly that a keyword reviewer misses it.

    If this test ever stops passing, the architecture no longer earns its cost.
    """
    finding = _missing_finding(liability_rule)
    client = StubClient(
        [
            canned(
                {
                    "verdict": "overturned",
                    "reasoning": "Located in General Provisions under different wording.",
                    "quotes": [CAP_QUOTE],
                }
            )
        ],
        name="gemini-stub",
    )

    result = await VerifierAgent(client, settings).challenge(finding, liability_rule, blocks)

    assert result.verdict is Verdict.OVERTURNED
    assert result.counter_citations[0].page == 3
    assert SearchStrategy.SYNONYM in result.strategies_used
    assert result.verifier_model == "gemini-stub"


async def test_verifier_confirms_a_genuine_absence(
    blocks: list[TextBlock], settings: Settings
) -> None:
    rule = ComplianceRule(
        rule_id="NDA-009",
        clause_name="Arbitration",
        domain="jurisdiction",
        description="Disputes must be referred to binding arbitration.",
        synonyms=["arbitration", "arbitral tribunal"],
    )
    finding = Finding(
        contract_id="NDA-8812",
        rule_id=rule.rule_id,
        clause_name=rule.clause_name,
        agent_name="jurisdiction_worker",
        status=FindingStatus.MISSING,
        rationale="No arbitration clause.",
        evidence=SearchEvidence(strategy=SearchStrategy.SEMANTIC, blocks_examined=9),
    )
    client = StubClient(
        [
            canned({"verdict": "confirmed", "reasoning": "No arbitration language.", "quotes": []})
            for _ in range(3)
        ],
        name="gemini-stub",
    )

    result = await VerifierAgent(client, settings).challenge(finding, rule, blocks)
    assert result.verdict is Verdict.CONFIRMED
    assert result.counter_citations == []


async def test_verifier_rejects_an_overturn_it_cannot_quote(
    blocks: list[TextBlock], liability_rule: ComplianceRule, settings: Settings
) -> None:
    """The verifier is held to the same evidentiary standard as the worker."""
    finding = _missing_finding(liability_rule)
    client = StubClient(
        [
            canned(
                {
                    "verdict": "overturned",
                    "reasoning": "I am sure it is in there.",
                    "quotes": ["Liability shall be capped at the contract value."],
                }
            ),
            canned({"verdict": "confirmed", "reasoning": "Nothing found.", "quotes": []}),
            canned({"verdict": "confirmed", "reasoning": "Nothing found.", "quotes": []}),
        ],
        name="gemini-stub",
    )

    result = await VerifierAgent(client, settings).challenge(finding, liability_rule, blocks)
    assert result.verdict is Verdict.NEEDS_HUMAN
    assert result.counter_citations == []


async def test_verifier_failure_never_reads_as_agreement(
    blocks: list[TextBlock], liability_rule: ComplianceRule, settings: Settings
) -> None:
    """A verifier that cannot run must escalate, not silently confirm."""
    finding = _missing_finding(liability_rule)
    client = StubClient([], name="gemini-stub")  # exhausted immediately

    result = await VerifierAgent(client, settings).challenge(finding, liability_rule, blocks)
    assert result.verdict is Verdict.NEEDS_HUMAN


async def test_verifier_respects_the_strategy_cap(
    blocks: list[TextBlock], liability_rule: ComplianceRule
) -> None:
    settings = Settings(max_verification_strategies=1)
    finding = _missing_finding(liability_rule)
    client = StubClient(
        [canned({"verdict": "confirmed", "reasoning": "Nothing.", "quotes": []})],
        name="gemini-stub",
    )

    result = await VerifierAgent(client, settings).challenge(finding, liability_rule, blocks)
    assert len(result.strategies_used) == 1
