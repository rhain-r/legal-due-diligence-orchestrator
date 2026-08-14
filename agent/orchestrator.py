"""The lead agent: plan, delegate, collect, escalate.

Flow for one audit:

    ingest -> plan chunk assignments -> dispatch workers concurrently
           -> route suspect findings to the verifier -> assemble report

Every step appends to `runs/<audit_id>/trace.jsonl`. The audit trail is a product
feature here, not debug output — a firm needs to show *why* the system concluded
a clause was missing, months later.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from agent.config import Settings, get_settings
from agent.ingestion import chunk_blocks, parse_pdf
from agent.ingestion.chunker import select_chunks_for_terms
from agent.ingestion.parser import page_count
from agent.llm import ModelClient, build_client
from agent.reporter import build_report
from agent.schemas import (
    AuditReport,
    Chunk,
    ComplianceRule,
    Finding,
    FindingStatus,
    TextBlock,
    Verdict,
    VerificationResult,
)
from agent.sop import load_sop
from agent.tools.search import coverage_summary
from agent.verifier import VerifierAgent
from agent.workers import build_workers

logger = logging.getLogger(__name__)


class Tracer:
    """Append-only JSONL trace of everything the agents did."""

    def __init__(self, audit_id: str, trace_dir: Path, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self.path = trace_dir / audit_id / "trace.jsonl"
        self.started = time.monotonic()
        if enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def emit(self, event: str, **payload: Any) -> None:
        if not self.enabled:
            return
        record = {
            "t": round(time.monotonic() - self.started, 3),
            "event": event,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


class Orchestrator:
    """Coordinates one audit end to end."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        worker_client: ModelClient | None = None,
        verifier_client: ModelClient | None = None,
        trace: bool = True,
    ) -> None:
        self.settings = settings or get_settings()
        self._worker_client = worker_client
        self._verifier_client = verifier_client
        self.trace_enabled = trace

    # --- Client resolution ---------------------------------------------------

    @property
    def worker_client(self) -> ModelClient:
        if self._worker_client is None:
            self._worker_client = build_client(self.settings, "worker")
        return self._worker_client

    @property
    def verifier_client(self) -> ModelClient:
        if self._verifier_client is None:
            self._verifier_client = build_client(self.settings, "verifier")
        return self._verifier_client

    # --- Planning ------------------------------------------------------------

    def plan_assignments(
        self, rules: list[ComplianceRule], chunks: list[Chunk]
    ) -> dict[str, list[Chunk]]:
        """Scope each rule to the chunks likely to contain it.

        Deliberately generous: `select_chunks_for_terms` falls back to the whole
        document when nothing matches, because a keyword miss is not evidence of
        absence. Over-assigning costs tokens; under-assigning manufactures the
        false absence claims this system exists to prevent.
        """
        return {rule.rule_id: select_chunks_for_terms(chunks, rule.search_terms) for rule in rules}

    # --- Execution -----------------------------------------------------------

    async def audit(
        self,
        pdf_path: str | Path,
        rules_path: str | Path = "nda_sop.yaml",
        *,
        contract_id: str | None = None,
    ) -> AuditReport:
        source = Path(pdf_path)
        contract_id = contract_id or source.stem.upper()

        sop = load_sop(rules_path)
        blocks = parse_pdf(source)
        chunks = chunk_blocks(
            blocks,
            target_chars=self.settings.chunk_target_chars,
            overlap_blocks=self.settings.chunk_overlap_blocks,
        )

        report_stub = AuditReport(
            contract_id=contract_id, source_file=source.name, rules_evaluated=len(sop.rules)
        )
        tracer = Tracer(report_stub.audit_id, self.settings.trace_dir, enabled=self.trace_enabled)
        tracer.emit(
            "ingested",
            contract_id=contract_id,
            sop=sop.name,
            chunks=len(chunks),
            **coverage_summary(blocks),
        )

        assignments = self.plan_assignments(sop.rules, chunks)
        tracer.emit(
            "planned",
            assignments={rid: [c.chunk_id for c in cs] for rid, cs in assignments.items()},
        )

        findings = await self._dispatch_workers(contract_id, sop.rules, assignments, tracer)
        verifications, surviving, overturned = await self._verify(
            findings, sop.rules, blocks, tracer
        )

        report = build_report(
            contract_id=contract_id,
            source_file=source.name,
            audit_id=report_stub.audit_id,
            rules_evaluated=len(sop.rules),
            findings=surviving,
            verifications=verifications,
            overturned=overturned,
            page_count=page_count(blocks),
        )
        tracer.emit(
            "completed",
            risk_score=report.risk_score,
            gaps=len(report.confirmed_gaps),
            overturned=report.verifier_lift,
        )
        return report

    async def _dispatch_workers(
        self,
        contract_id: str,
        rules: list[ComplianceRule],
        assignments: dict[str, list[Chunk]],
        tracer: Tracer,
    ) -> list[Finding]:
        """Run workers concurrently, bounded by a semaphore."""
        workers = build_workers(rules, self.worker_client)
        semaphore = asyncio.Semaphore(self.settings.worker_concurrency)

        async def run_one(worker) -> Finding | None:
            async with semaphore:
                chunks = assignments.get(worker.rule.rule_id, [])
                tracer.emit(
                    "dispatch",
                    agent=worker.name,
                    rule_id=worker.rule.rule_id,
                    chunks=[c.chunk_id for c in chunks],
                )
                try:
                    finding = await worker.run(contract_id, chunks)
                except Exception as exc:
                    logger.exception("Worker %s failed on %s", worker.name, worker.rule.rule_id)
                    tracer.emit(
                        "worker_error",
                        agent=worker.name,
                        rule_id=worker.rule.rule_id,
                        error=str(exc),
                    )
                    return None
                tracer.emit(
                    "finding",
                    agent=worker.name,
                    rule_id=finding.rule_id,
                    status=finding.status.value,
                    confidence=finding.confidence,
                    citations=len(finding.citations),
                )
                return finding

        results = await asyncio.gather(*(run_one(w) for w in workers))
        return [f for f in results if f is not None]

    async def _verify(
        self,
        findings: list[Finding],
        rules: list[ComplianceRule],
        blocks: list[TextBlock],
        tracer: Tracer,
    ) -> tuple[list[VerificationResult], list[Finding], list[Finding]]:
        """Challenge every suspect finding. Returns (results, surviving, overturned)."""
        rules_by_id = {r.rule_id: r for r in rules}
        verifier = VerifierAgent(self.verifier_client, self.settings)

        to_check = [f for f in findings if f.needs_verification]
        tracer.emit("verification_queue", count=len(to_check), total_findings=len(findings))

        semaphore = asyncio.Semaphore(self.settings.worker_concurrency)

        async def challenge_one(finding: Finding) -> VerificationResult | None:
            async with semaphore:
                rule = rules_by_id.get(finding.rule_id)
                if rule is None:
                    return None
                result = await verifier.challenge(finding, rule, blocks)
                tracer.emit(
                    "verification",
                    finding_id=finding.finding_id,
                    rule_id=finding.rule_id,
                    verdict=result.verdict.value,
                    strategies=[s.value for s in result.strategies_used],
                )
                return result

        results = [r for r in await asyncio.gather(*(challenge_one(f) for f in to_check)) if r]
        verdicts = {r.finding_id: r for r in results}

        surviving: list[Finding] = []
        overturned: list[Finding] = []

        for finding in findings:
            result = verdicts.get(finding.finding_id)
            if result is None or result.verdict is Verdict.CONFIRMED:
                surviving.append(finding)
            elif result.verdict is Verdict.OVERTURNED:
                # The clause was located after all. Rewrite the finding rather than
                # discarding it, and keep the original in the audit trail.
                overturned.append(finding)
                surviving.append(
                    finding.model_copy(
                        update={
                            "status": FindingStatus.PRESENT,
                            "citations": result.counter_citations,
                            "evidence": None,
                            "rationale": f"[overturned by verifier] {result.reasoning}",
                            "confidence": 0.9,
                            "agent_name": "verifier",
                        }
                    )
                )
            else:  # NEEDS_HUMAN
                surviving.append(
                    finding.model_copy(
                        update={
                            "status": FindingStatus.AMBIGUOUS
                            if finding.citations
                            else FindingStatus.MISSING,
                            "rationale": f"[needs human review] {result.reasoning}",
                            "confidence": 0.5,
                        }
                    )
                )

        return results, surviving, overturned


async def run_audit(
    pdf_path: str | Path,
    rules_path: str | Path = "nda_sop.yaml",
    *,
    settings: Settings | None = None,
) -> AuditReport:
    """Convenience wrapper for a single audit."""
    return await Orchestrator(settings).audit(pdf_path, rules_path)
