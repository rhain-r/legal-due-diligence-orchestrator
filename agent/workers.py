"""Clause worker agents.

A worker owns exactly one compliance rule and sees only the chunks assigned to it.
Bounded scope keeps cost predictable and keeps the model's attention on the clause
in question.

Note how thin this module is: the schema, the citation gate, and the retrieval
tools do the load-bearing work. If writing a new worker ever feels hard, something
underneath it is missing.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from agent.config import load_prompt
from agent.llm import ModelClient, complete_structured
from agent.schemas import (
    Chunk,
    ComplianceRule,
    Finding,
    FindingStatus,
    SearchEvidence,
    SearchStrategy,
    TextBlock,
)
from agent.tools.citation import CitationError, cite_from_blocks

logger = logging.getLogger(__name__)


class WorkerResponse(BaseModel):
    """Raw model output, before it is promoted to a validated Finding."""

    model_config = ConfigDict(extra="ignore")

    status: FindingStatus
    rationale: str
    quotes: list[str] = Field(default_factory=list)
    terms_searched: list[str] = Field(default_factory=list)
    sections_scanned: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ClauseWorker:
    """Audits one rule against one set of chunks."""

    def __init__(
        self, rule: ComplianceRule, client: ModelClient, *, max_tokens: int = 2048
    ) -> None:
        self.rule = rule
        self.client = client
        self.max_tokens = max_tokens
        self.name = f"{rule.domain.lower()}_worker"

    def _system_prompt(self) -> str:
        return load_prompt("worker").format(
            domain=self.rule.domain,
            rule_id=self.rule.rule_id,
            clause_name=self.rule.clause_name,
            description=self.rule.description,
            synonyms=", ".join(self.rule.synonyms) or "(none listed)",
        )

    async def run(self, contract_id: str, chunks: list[Chunk]) -> Finding:
        """Audit the rule and return a validated Finding.

        Quotes are verified against the source before becoming citations. If the
        model claims a clause is present but cannot quote it accurately, the
        finding is downgraded rather than trusted — an unverifiable quote is
        indistinguishable from a fabricated one.
        """
        blocks = [b for chunk in chunks for b in chunk.blocks]
        excerpt = "\n\n---\n\n".join(chunk.render() for chunk in chunks)

        response = await complete_structured(
            self.client,
            self._system_prompt(),
            f"## Contract excerpts\n\n{excerpt}",
            WorkerResponse,
            max_tokens=self.max_tokens,
        )

        return self._to_finding(contract_id, response, blocks)

    def _to_finding(
        self, contract_id: str, response: WorkerResponse, blocks: list[TextBlock]
    ) -> Finding:
        status = response.status
        citations = []
        confidence = response.confidence
        rationale = response.rationale

        if status is not FindingStatus.MISSING:
            for quote in response.quotes:
                try:
                    citations.append(cite_from_blocks(blocks, quote))
                except CitationError as exc:
                    logger.warning("[%s] rejected unverifiable quote: %s", self.name, exc)

            if not citations:
                # The model asserted a clause it cannot point to. Do not report it
                # as found; hand it to the verifier as an unsupported claim.
                logger.warning(
                    "[%s] %s claimed %s with no verifiable quote — downgrading to ambiguous",
                    self.name,
                    self.rule.rule_id,
                    status.value,
                )
                status = FindingStatus.AMBIGUOUS
                confidence = min(confidence, 0.3)
                rationale = f"[unverifiable quotes; downgraded] {rationale}"

        # An ambiguous finding with no citations is structurally an absence claim,
        # so it must carry the same evidentiary burden.
        needs_evidence = status is FindingStatus.MISSING or not citations
        evidence = (
            SearchEvidence(
                strategy=SearchStrategy.SEMANTIC,
                terms_searched=response.terms_searched or self.rule.search_terms,
                sections_scanned=response.sections_scanned,
                blocks_examined=len(blocks),
            )
            if needs_evidence
            else None
        )

        if status is FindingStatus.AMBIGUOUS and not citations:
            status = FindingStatus.MISSING

        return Finding(
            contract_id=contract_id,
            rule_id=self.rule.rule_id,
            clause_name=self.rule.clause_name,
            agent_name=self.name,
            status=status,
            severity=self.rule.severity,
            rationale=rationale,
            citations=citations,
            evidence=evidence,
            confidence=confidence,
        )


def build_workers(rules: list[ComplianceRule], client: ModelClient) -> list[ClauseWorker]:
    """One worker per rule, sharing a model client."""
    return [ClauseWorker(rule, client) for rule in rules]
