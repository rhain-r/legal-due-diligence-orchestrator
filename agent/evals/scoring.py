"""Metrics.

The positive class is **"the system says this obligation is not satisfied"** —
an absence claim. That framing puts the two errors that matter in this domain on
opposite sides of the confusion matrix:

- **False positive** — claimed absent, actually present. The credibility killer.
  Send a client a report saying their cap on damages is missing when it is in
  clause 18, and they stop trusting the tool entirely.
- **False negative** — claimed present (or not flagged), actually absent. The
  liability killer. Nobody notices until it matters.

`AMBIGUOUS` and `NON_COMPLIANT` count as absence claims: in each case the system
is saying the obligation is not cleanly satisfied, which is what a reviewer acts
on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from agent.evals import GOLDEN_DIR
from agent.schemas import AuditReport, Finding, FindingStatus


class Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    expected: Literal["present", "absent"]
    location: str | None = None
    note: str | None = None


class AnswerKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: str
    source: str
    title: str
    purpose: str
    expectations: list[Expectation]

    @property
    def by_rule(self) -> dict[str, Expectation]:
        return {e.rule_id: e for e in self.expectations}


def load_answer_keys(golden_dir: Path = GOLDEN_DIR) -> list[AnswerKey]:
    """Load every answer key, sorted by filename for stable reporting."""
    keys = [
        AnswerKey.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
        for p in sorted(golden_dir.glob("*.yaml"))
    ]
    if not keys:
        raise FileNotFoundError(f"No answer keys found in {golden_dir}")
    return keys


def claims_absent(status: FindingStatus) -> bool:
    """Whether a finding asserts the obligation is not cleanly satisfied."""
    return status is not FindingStatus.PRESENT


@dataclass
class Confusion:
    """Counts plus the derived rates."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return round(self.tp / denom, 3) if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return round(self.tp / denom, 3) if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return round(2 * p * r / (p + r), 3) if (p + r) else 0.0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.fn + self.tn

    def add(self, *, claimed: bool, truly_absent: bool) -> None:
        if claimed and truly_absent:
            self.tp += 1
        elif claimed and not truly_absent:
            self.fp += 1
        elif not claimed and truly_absent:
            self.fn += 1
        else:
            self.tn += 1

    def merge(self, other: Confusion) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn
        self.tn += other.tn

    def as_dict(self) -> dict:
        return {
            "tp": self.tp,
            "fp_credibility_killer": self.fp,
            "fn_liability_killer": self.fn,
            "tn": self.tn,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass
class VerifierLift:
    """Whether the verification loop earned its cost."""

    overturns: int = 0
    overturns_correct: int = 0
    overturns_incorrect: int = 0
    needs_human: int = 0

    def merge(self, other: VerifierLift) -> None:
        self.overturns += other.overturns
        self.overturns_correct += other.overturns_correct
        self.overturns_incorrect += other.overturns_incorrect
        self.needs_human += other.needs_human

    def as_dict(self) -> dict:
        return {
            "overturns": self.overturns,
            "overturns_correct": self.overturns_correct,
            "overturns_incorrect": self.overturns_incorrect,
            "needs_human": self.needs_human,
        }


@dataclass
class ContractScore:
    contract_id: str
    title: str
    with_verification: Confusion = field(default_factory=Confusion)
    without_verification: Confusion = field(default_factory=Confusion)
    lift: VerifierLift = field(default_factory=VerifierLift)
    missing_findings: list[str] = field(default_factory=list)
    detail: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "contract_id": self.contract_id,
            "title": self.title,
            "with_verification": self.with_verification.as_dict(),
            "without_verification": self.without_verification.as_dict(),
            "verifier_lift": self.lift.as_dict(),
            "rules_without_a_finding": self.missing_findings,
            "detail": self.detail,
        }


def reconstruct_pre_verification(report: AuditReport) -> dict[str, Finding]:
    """The findings as the workers left them, before the verifier ran.

    `report.overturned` holds the original objects, and `model_copy` preserves
    `finding_id`, so the pre-verification view is recoverable without a second run.
    """
    originals = {f.finding_id: f for f in report.overturned}
    return {
        f.rule_id: originals.get(f.finding_id, f)
        for f in report.findings
    }


def score_contract(report: AuditReport, key: AnswerKey) -> ContractScore:
    """Score one audit against its answer key."""
    score = ContractScore(contract_id=key.contract_id, title=key.title)

    post = {f.rule_id: f for f in report.findings}
    pre = reconstruct_pre_verification(report)
    overturned_rules = {f.rule_id for f in report.overturned}
    needs_human_ids = {
        v.finding_id for v in report.verifications if v.verdict.value == "needs_human"
    }

    for expectation in key.expectations:
        finding = post.get(expectation.rule_id)
        if finding is None:
            # A worker crashed. Not scored — silently counting it as a pass or a
            # fail would both misrepresent what happened.
            score.missing_findings.append(expectation.rule_id)
            continue

        truly_absent = expectation.expected == "absent"
        claimed_after = claims_absent(finding.status)
        claimed_before = claims_absent(pre[expectation.rule_id].status)

        score.with_verification.add(claimed=claimed_after, truly_absent=truly_absent)
        score.without_verification.add(claimed=claimed_before, truly_absent=truly_absent)

        if expectation.rule_id in overturned_rules:
            score.lift.overturns += 1
            if truly_absent:
                score.lift.overturns_incorrect += 1
            else:
                score.lift.overturns_correct += 1

        if finding.finding_id in needs_human_ids:
            score.lift.needs_human += 1

        outcome = _outcome(claimed_after, truly_absent)
        score.detail.append(
            {
                "rule_id": expectation.rule_id,
                "clause": finding.clause_name,
                "expected": expectation.expected,
                "worker_status": pre[expectation.rule_id].status.value,
                "final_status": finding.status.value,
                "outcome": outcome,
                "overturned": expectation.rule_id in overturned_rules,
                "note": expectation.note,
            }
        )

    return score


def _outcome(claimed: bool, truly_absent: bool) -> str:
    if claimed and truly_absent:
        return "correct_gap"
    if claimed and not truly_absent:
        return "FALSE_POSITIVE"
    if not claimed and truly_absent:
        return "FALSE_NEGATIVE"
    return "correct_clean"


def aggregate(scores: list[ContractScore]) -> tuple[Confusion, Confusion, VerifierLift]:
    with_v, without_v, lift = Confusion(), Confusion(), VerifierLift()
    for s in scores:
        with_v.merge(s.with_verification)
        without_v.merge(s.without_verification)
        lift.merge(s.lift)
    return with_v, without_v, lift
