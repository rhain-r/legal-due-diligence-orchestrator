"""The verification loop. This module is why the project exists.

Three properties make verification real rather than ceremonial:

1. **Different strategy.** The worker read semantically over assigned chunks. The
   verifier runs synonym expansion and section scans over the *entire* document.
2. **Different model.** The verifier runs on Gemini while workers run on Claude.
   Two independently trained models converging on "absent" is evidence; one model
   agreeing with itself is not.
3. **Inverted burden of proof.** The verifier's job is to *find* the clause, not to
   confirm its absence. A single genuine hit overturns the finding.

A verifier that never overturns anything is a verifier that is not running.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field

from agent.config import Settings, load_prompt
from agent.llm import ModelClient, ModelError, complete_structured
from agent.schemas import (
    ComplianceRule,
    Finding,
    FindingStatus,
    SearchStrategy,
    TextBlock,
    Verdict,
    VerificationResult,
)
from agent.tools.citation import CitationError, cite_from_blocks
from agent.tools.search import section_scan, synonym_search

logger = logging.getLogger(__name__)


class VerifierResponse(BaseModel):
    """Raw verifier output, before quote verification."""

    model_config = ConfigDict(extra="ignore")

    verdict: Verdict
    reasoning: str
    quotes: list[str] = Field(default_factory=list)


class VerifierAgent:
    """Challenges findings by trying to disprove them."""

    def __init__(self, client: ModelClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings
        self.name = "verifier"

    def _system_prompt(self, rule: ComplianceRule, finding: Finding) -> str:
        terms = finding.evidence.terms_searched if finding.evidence else []
        base_prompt = load_prompt("verifier").format(
            clause_name=rule.clause_name,
            description=rule.description,
            rationale=finding.rationale,
            terms_searched=", ".join(terms) or "(not recorded)",
        )
        
        # Append specific instructions based on what we are trying to disprove
       # Append specific instructions based on what we are trying to disprove
        if finding.status == FindingStatus.PRESENT:
            return base_prompt + (
                "\n\nThe worker claims this clause is PRESENT. Your job is to PROVE "
                "THEM WRONG by finding negations, loopholes, or fine print that "
                "invalidates their claim."
            )
        else:
            return base_prompt + (
                "\n\nThe worker claims this clause is MISSING. Your job is to PROVE "
                "THEM WRONG by finding the clause hidden in the text."
            )
    def _candidate_ladder(
        self, rule: ComplianceRule, blocks: list[TextBlock]
    ) -> list[tuple[SearchStrategy, list[TextBlock]]]:
        """Escalating retrieval strategies, cheapest and most targeted first."""
        ladder: list[tuple[SearchStrategy, list[TextBlock]]] = []

        synonym_hits = synonym_search(blocks, rule)
        if synonym_hits:
            ladder.append((SearchStrategy.SYNONYM, synonym_hits))

        # Standard protections are routinely buried in catch-all sections.
        catchall = section_scan(blocks, r"general|miscellaneous|other\s+terms|additional")
        if catchall:
            ladder.append((SearchStrategy.SECTION_SCAN, catchall))

        # Last resort: the whole document, one narrow question.
        ladder.append((SearchStrategy.FULL_TEXT, blocks))

        return ladder[: self.settings.max_verification_strategies]

    async def challenge(
        self, finding: Finding, rule: ComplianceRule, blocks: list[TextBlock]
    ) -> VerificationResult:
        """Attempt to overturn `finding`. Stops at the first genuine hit."""
        strategies_used: list[SearchStrategy] = []
        system = self._system_prompt(rule, finding)
        ambiguous_reasoning: str | None = None

        for strategy, candidates in self._candidate_ladder(rule, blocks):
            strategies_used.append(strategy)
            excerpt = "\n\n".join(f"[{b.block_id} | {b.locator}]\n{b.text}" for b in candidates)

            try:
                # Dynamically set the question based on the claim
               # Dynamically set the question based on the claim
                if finding.status == FindingStatus.PRESENT:
                    question = (
                        f"## Retrieval strategy: {strategy.value}\n"
                        f"## Blocks retrieved: {len(candidates)}\n\n"
                        f"{excerpt}\n\n"
                        "Read carefully. Does any language above explicitly negate, "
                        f"invalidate, or loophole this obligation: {rule.description}?"
                    )
                else:
                    question = (
                        f"## Retrieval strategy: {strategy.value}\n"
                        f"## Blocks retrieved: {len(candidates)}\n\n"
                        f"{excerpt}\n\n"
                        f"Does any language above create this obligation: {rule.description}?"
                    )

                response = await complete_structured(
                    self.client,
                    system,
                    question,
                    VerifierResponse,
                    max_tokens=self.settings.max_output_tokens,
                )
            except ModelError as exc:
                # A verifier that cannot run must not be read as agreement.
                logger.error("Verifier failed on %s via %s: %s", finding.finding_id, strategy, exc)
                return VerificationResult(
                    finding_id=finding.finding_id,
                    verdict=Verdict.NEEDS_HUMAN,
                    strategies_used=strategies_used,
                    reasoning=(
                        f"Verification could not complete ({exc}). "
                        "Escalated for human review."
                    ),
                    verifier_model=self.client.name,
                )

            if response.verdict is Verdict.OVERTURNED:
                counter = self._verify_quotes(response.quotes, candidates)
                if counter:
                    logger.info(
                        "Verifier OVERTURNED %s (%s) via %s",
                        finding.finding_id,
                        rule.clause_name,
                        strategy.value,
                    )
                    return VerificationResult(
                        finding_id=finding.finding_id,
                        verdict=Verdict.OVERTURNED,
                        strategies_used=strategies_used,
                        counter_citations=counter,
                        reasoning=response.reasoning,
                        verifier_model=self.client.name,
                    )
                # Claimed to find it but could not quote it. That is not a hit.
                logger.warning(
                    "Verifier claimed overturn on %s with no verifiable quote; continuing ladder",
                    finding.finding_id,
                )
                ambiguous_reasoning = response.reasoning

            elif response.verdict is Verdict.NEEDS_HUMAN:
                ambiguous_reasoning = response.reasoning

        if ambiguous_reasoning:
            return VerificationResult(
                finding_id=finding.finding_id,
                verdict=Verdict.NEEDS_HUMAN,
                strategies_used=strategies_used,
                reasoning=ambiguous_reasoning,
                verifier_model=self.client.name,
            )

        # Determine the correct confirmation message
# Determine the correct confirmation message
        if finding.status == FindingStatus.PRESENT:
            final_reasoning = (
                f"Reviewed via {', '.join(s.value for s in strategies_used)} across "
                f"{len(blocks)} blocks. The clause appears valid; no negations or "
                "loopholes were found."
            )
        else:
            final_reasoning = (
                f"Searched via {', '.join(s.value for s in strategies_used)} across "
                f"{len(blocks)} blocks. No language creating this obligation was located."
            )

        return VerificationResult(
            finding_id=finding.finding_id,
            verdict=Verdict.CONFIRMED,
            strategies_used=strategies_used,
            reasoning=final_reasoning,
            verifier_model=self.client.name,
        )

    @staticmethod
    def _verify_quotes(quotes: list[str], blocks: list[TextBlock]) -> list:
        """Keep only quotes that actually appear in the retrieved blocks."""
        verified = []
        for quote in quotes:
            try:
                verified.append(cite_from_blocks(blocks, quote))
            except CitationError as exc:
                logger.warning("Verifier quote rejected: %s", exc)
        return verified
