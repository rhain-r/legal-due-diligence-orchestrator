"""The eval harness is only useful if its scoring is trustworthy.

These tests target the metric definitions and the consistency of the golden set.
A scorer with an off-by-one in the confusion matrix would produce confident,
wrong numbers — the exact failure this project is about.
"""

from __future__ import annotations

import pytest

from agent.evals.corpus import CONTRACTS, pages_for
from agent.evals.scoring import (
    Confusion,
    claims_absent,
    load_answer_keys,
    reconstruct_pre_verification,
)
from agent.evals.simulated import (
    SimulatedVerifierClient,
    SimulatedWorkerClient,
    WorkerStrength,
    parse_blocks,
    parse_clause_name,
)
from agent.ingestion.chunker import chunk_blocks
from agent.schemas import (
    AuditReport,
    Citation,
    ComplianceRule,
    Finding,
    FindingStatus,
    SearchEvidence,
    SearchStrategy,
)
from agent.sop import load_sop

# --- Metric definitions ------------------------------------------------------


def test_confusion_counts_the_four_outcomes() -> None:
    c = Confusion()
    c.add(claimed=True, truly_absent=True)  # correct gap
    c.add(claimed=True, truly_absent=False)  # credibility killer
    c.add(claimed=False, truly_absent=True)  # liability killer
    c.add(claimed=False, truly_absent=False)  # correct clean
    assert (c.tp, c.fp, c.fn, c.tn) == (1, 1, 1, 1)
    assert c.precision == 0.5
    assert c.recall == 0.5
    assert c.f1 == 0.5


def test_perfect_score() -> None:
    c = Confusion(tp=4, fp=0, fn=0, tn=4)
    assert c.precision == 1.0
    assert c.recall == 1.0
    assert c.f1 == 1.0


def test_no_claims_does_not_divide_by_zero() -> None:
    c = Confusion(tp=0, fp=0, fn=3, tn=5)
    assert c.precision == 0.0
    assert c.recall == 0.0
    assert c.f1 == 0.0


def test_non_compliant_and_ambiguous_count_as_absence_claims() -> None:
    """Each says the obligation is not cleanly satisfied, which is what a
    reviewer acts on."""
    assert claims_absent(FindingStatus.MISSING) is True
    assert claims_absent(FindingStatus.NON_COMPLIANT) is True
    assert claims_absent(FindingStatus.AMBIGUOUS) is True
    assert claims_absent(FindingStatus.PRESENT) is False


def test_pre_verification_view_recovers_the_original_status() -> None:
    """Without this, verifier lift cannot be measured from a single run."""
    original = Finding(
        contract_id="C1",
        rule_id="NDA-006",
        clause_name="Cap on Damages",
        agent_name="liability_worker",
        status=FindingStatus.MISSING,
        rationale="not found",
        evidence=SearchEvidence(strategy=SearchStrategy.SEMANTIC, blocks_examined=4),
    )
    rewritten = original.model_copy(
        update={
            "status": FindingStatus.PRESENT,
            "citations": [Citation(page=1, paragraph=0, quote="shall not exceed")],
            "evidence": None,
        }
    )
    report = AuditReport(
        contract_id="C1",
        source_file="c1.pdf",
        rules_evaluated=1,
        findings=[rewritten],
        overturned=[original],
    )
    pre = reconstruct_pre_verification(report)
    assert pre["NDA-006"].status is FindingStatus.MISSING


# --- Golden set consistency --------------------------------------------------


def test_every_answer_key_loads() -> None:
    keys = load_answer_keys()
    assert len(keys) >= 5


def test_answer_keys_cover_every_sop_rule() -> None:
    """A rule with no expectation is silently unscored, which would inflate
    nothing but hide a real gap in coverage."""
    rule_ids = {r.rule_id for r in load_sop("nda_sop.yaml").rules}
    for key in load_answer_keys():
        covered = set(key.by_rule)
        assert covered == rule_ids, f"{key.contract_id} does not cover {rule_ids - covered}"


def test_answer_keys_reference_a_real_contract() -> None:
    for key in load_answer_keys():
        assert key.source in CONTRACTS


def test_golden_set_contains_both_error_traps() -> None:
    """An eval where everything is present cannot measure recall."""
    all_expectations = [e for key in load_answer_keys() for e in key.expectations]
    assert any(e.expected == "absent" for e in all_expectations)
    assert any(e.expected == "present" for e in all_expectations)


def test_contracts_split_into_pages() -> None:
    for name in CONTRACTS:
        pages = pages_for(name)
        assert pages and all(pages)


# --- Simulated agents --------------------------------------------------------


def test_prompt_parsing_round_trips(blocks) -> None:
    rendered = chunk_blocks(blocks)[0].render()
    parsed = parse_blocks(rendered)
    assert len(parsed) == len(blocks)
    assert parsed[0][0] == blocks[0].block_id


def test_clause_name_is_recovered_from_the_system_prompt() -> None:
    system = "- **Clause:** Cap on Damages\n- **Requirement:** something"
    assert parse_clause_name(system) == "Cap on Damages"


async def test_simulated_worker_misses_a_renamed_clause(
    blocks, liability_rule: ComplianceRule
) -> None:
    """The failure mode the verifier exists to catch, reproduced deterministically."""
    from agent.workers import ClauseWorker

    client = SimulatedWorkerClient([liability_rule], WorkerStrength.NAIVE)
    finding = await ClauseWorker(liability_rule, client).run("C1", chunk_blocks(blocks))
    assert finding.status is FindingStatus.MISSING


async def test_simulated_verifier_finds_what_the_worker_missed(
    blocks, liability_rule: ComplianceRule, settings
) -> None:
    from agent.verifier import VerifierAgent

    finding = Finding(
        contract_id="C1",
        rule_id=liability_rule.rule_id,
        clause_name=liability_rule.clause_name,
        agent_name="liability_worker",
        status=FindingStatus.MISSING,
        rationale="not found",
        evidence=SearchEvidence(strategy=SearchStrategy.SEMANTIC, blocks_examined=9),
    )
    verifier = VerifierAgent(SimulatedVerifierClient([liability_rule]), settings)
    result = await verifier.challenge(finding, liability_rule, blocks)
    assert result.verdict.value == "overturned"
    assert result.counter_citations


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The Receiving Party shall return or destroy all materials.", True),
        ("The Parties acknowledge the importance of information hygiene.", False),
        ("The Receiving Party shall have no obligation to return or destroy.", False),
        ("Return of Materials", False),
    ],
)
def test_verifier_distinguishes_obligation_from_topic(text: str, expected: bool) -> None:
    """Mentioning a topic is not creating a duty; a cancelled duty is not a duty."""
    rule = ComplianceRule(
        rule_id="NDA-004",
        clause_name="Return or Destruction of Materials",
        domain="confidentiality",
        description="Materials must be returned or destroyed.",
        synonyms=["return or destroy"],
    )
    client = SimulatedVerifierClient([rule])
    tokens = ["return", "destruction", "materials"]
    assert client._is_operative(text, tokens, ["return or destroy"]) is expected
