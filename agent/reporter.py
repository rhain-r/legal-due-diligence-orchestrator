"""Report assembly and rendering.

The risk score is computed in plain Python, not asked of a model. A scoring
function can be audited, explained to a client, and unit-tested. An LLM's "7.5"
can be none of those things.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.schemas import (
    SEVERITY_WEIGHT,
    AuditReport,
    Finding,
    FindingStatus,
    Verdict,
    VerificationResult,
)

#: Statuses that count against the contract, and how heavily.
_STATUS_MULTIPLIER: dict[FindingStatus, float] = {
    FindingStatus.MISSING: 1.0,
    FindingStatus.NON_COMPLIANT: 0.8,
    FindingStatus.AMBIGUOUS: 0.4,
    FindingStatus.PRESENT: 0.0,
}

_STATUS_STYLE: dict[FindingStatus, str] = {
    FindingStatus.MISSING: "bold red",
    FindingStatus.NON_COMPLIANT: "red",
    FindingStatus.AMBIGUOUS: "yellow",
    FindingStatus.PRESENT: "green",
}


def compute_risk_score(findings: list[Finding]) -> float:
    """Weighted share of achievable risk, 0 (clean) to 100 (every critical gap).

    Normalised against the maximum possible score for this rule set, so a contract
    audited under an 8-rule SOP is comparable to one audited under 40 rules.
    """
    if not findings:
        return 0.0
    max_possible = sum(SEVERITY_WEIGHT[f.severity] for f in findings)
    if max_possible == 0:
        return 0.0
    incurred = sum(
        SEVERITY_WEIGHT[f.severity] * _STATUS_MULTIPLIER.get(f.status, 0.0) for f in findings
    )
    return round(min(100.0, (incurred / max_possible) * 100), 1)


def build_report(
    *,
    contract_id: str,
    source_file: str,
    audit_id: str,
    rules_evaluated: int,
    findings: list[Finding],
    verifications: list[VerificationResult],
    overturned: list[Finding],
    page_count: int = 0,
) -> AuditReport:
    """Assemble the final validated report."""
    # Derived from verdicts, not from rendered prose. Substring-matching the
    # rationale would silently stop working the moment the orchestrator reworded
    # its prefix, and escalated findings would quietly read as settled.
    escalated_ids = {v.finding_id for v in verifications if v.verdict is Verdict.NEEDS_HUMAN}
    unresolved = [
        f.rule_id
        for f in findings
        if f.status is FindingStatus.AMBIGUOUS or f.finding_id in escalated_ids
    ]
    return AuditReport(
        audit_id=audit_id,
        contract_id=contract_id,
        source_file=source_file,
        rules_evaluated=rules_evaluated,
        findings=findings,
        verifications=verifications,
        overturned=overturned,
        unresolved=sorted(set(unresolved)),
        risk_score=compute_risk_score(findings),
        page_count=page_count,
    )


def write_json(report: AuditReport, out_dir: Path) -> Path:
    """Persist the strict-schema report."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.audit_id}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def render_terminal(report: AuditReport, console: Console | None = None) -> None:
    """Human-readable summary for the terminal."""
    console = console or Console()

    if report.risk_score >= 50:
        risk_style = "red"
    elif report.risk_score >= 20:
        risk_style = "yellow"
    else:
        risk_style = "green"
    console.print(
        Panel(
            f"[bold]{report.contract_id}[/bold]  ·  {report.source_file}  ·  "
            f"{report.page_count} pages  ·  {report.rules_evaluated} rules\n"
            f"Risk score: [{risk_style}]{report.risk_score}/100[/{risk_style}]   "
            f"Confirmed gaps: {len(report.confirmed_gaps)}   "
            f"Verifier overturns: {report.verifier_lift}",
            title="Audit complete",
            border_style=risk_style,
        )
    )

    table = Table(show_lines=False, header_style="bold")
    table.add_column("Rule", style="dim", no_wrap=True)
    table.add_column("Clause")
    table.add_column("Status", no_wrap=True)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Location / Evidence")

    for finding in sorted(report.findings, key=lambda f: (f.status.value, f.rule_id)):
        if finding.citations:
            where = ", ".join(str(c) for c in finding.citations[:2])
        elif finding.evidence:
            where = f"{finding.evidence.blocks_examined} blocks, {finding.evidence.strategy.value}"
        else:
            where = "—"
        table.add_row(
            finding.rule_id,
            finding.clause_name,
            f"[{_STATUS_STYLE[finding.status]}]{finding.status.value}[/]",
            finding.severity.value,
            where,
        )

    console.print(table)

    if report.verifier_lift:
        console.print(
            f"\n[dim]The verifier overturned {report.verifier_lift} finding(s) that a "
            "single-pass review would have reported as missing.[/dim]"
        )
    if report.unresolved:
        console.print(f"[yellow]Needs human review:[/yellow] {', '.join(report.unresolved)}")


def render_markdown(report: AuditReport) -> str:
    """Memo-style summary a lawyer would actually read."""
    lines = [
        f"# Due Diligence Report — {report.contract_id}",
        "",
        f"**Source:** {report.source_file} ({report.page_count} pages)  ",
        f"**Audit ID:** `{report.audit_id}`  ",
        f"**Generated:** {report.generated_at:%Y-%m-%d %H:%M UTC}  ",
        f"**Risk score:** {report.risk_score}/100",
        "",
        "## Gaps requiring attention",
        "",
    ]

    gaps = [f for f in report.findings if f.status is not FindingStatus.PRESENT]
    if not gaps:
        lines.append("None. Every rule in the SOP was satisfied.")
    else:
        lines.append("| Rule | Clause | Status | Severity | Notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        for f in sorted(gaps, key=lambda f: SEVERITY_WEIGHT[f.severity], reverse=True):
            note = f.rationale.replace("\n", " ")[:160]
            lines.append(
                f"| {f.rule_id} | {f.clause_name} | {f.status.value} "
                f"| {f.severity.value} | {note} |"
            )

    satisfied = [f for f in report.findings if f.status is FindingStatus.PRESENT]
    if satisfied:
        lines += ["", "## Satisfied", ""]
        for f in satisfied:
            loc = str(f.citations[0]) if f.citations else "—"
            lines.append(f"- **{f.clause_name}** — {loc}")

    if report.overturned:
        lines += [
            "",
            "## Audit trail — findings the verifier overturned",
            "",
            "These were reported as missing by a worker agent, then located by the "
            "verifier using a different search strategy. Retained for transparency.",
            "",
        ]
        for f in report.overturned:
            lines.append(
                f"- **{f.clause_name}** ({f.rule_id}) — claimed missing by `{f.agent_name}`"
            )

    return "\n".join(lines) + "\n"


def write_markdown(report: AuditReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report.audit_id}.md"
    path.write_text(render_markdown(report), encoding="utf-8")
    return path


def load_report(path: str | Path) -> AuditReport:
    """Round-trip a persisted report back into a validated object."""
    return AuditReport.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
