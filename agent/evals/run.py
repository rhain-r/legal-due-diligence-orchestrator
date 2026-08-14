"""Run the golden set and report.

    uv run python -m agent.evals.run                    # simulated, naive worker
    uv run python -m agent.evals.run --strength synonym # stronger worker
    uv run python -m agent.evals.run --live             # real models, needs keys

Every number printed by the default mode comes from deterministic stand-ins, not
models. See `simulated.py` for what that does and does not measure.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from agent.config import Settings
from agent.evals import BUILD_DIR, RESULTS_DIR
from agent.evals.generate import build_contract
from agent.evals.scoring import (
    AnswerKey,
    ContractScore,
    aggregate,
    load_answer_keys,
    score_contract,
)
from agent.evals.simulated import (
    SimulatedVerifierClient,
    SimulatedWorkerClient,
    WorkerStrength,
)
from agent.orchestrator import Orchestrator
from agent.sop import load_sop

app = typer.Typer(add_completion=False, help="Evaluate the pipeline against golden contracts.")


async def _run_one(
    key: AnswerKey,
    pdf: Path,
    rules_path: str,
    settings: Settings,
    *,
    live: bool,
    strength: WorkerStrength,
) -> ContractScore:
    rules = load_sop(rules_path).rules
    orchestrator = Orchestrator(
        settings,
        worker_client=None if live else SimulatedWorkerClient(rules, strength),
        verifier_client=None if live else SimulatedVerifierClient(rules),
        trace=False,
    )
    report = await orchestrator.audit(pdf, rules_path, contract_id=key.contract_id)
    return score_contract(report, key)


async def _run_all(
    rules_path: str, *, live: bool, strength: WorkerStrength
) -> list[ContractScore]:
    settings = Settings()
    keys = load_answer_keys()
    scores: list[ContractScore] = []
    for key in keys:
        pdf = build_contract(key.source, BUILD_DIR)
        scores.append(await _run_one(key, pdf, rules_path, settings, live=live, strength=strength))
    return scores


def render_markdown(scores: list[ContractScore], *, live: bool, strength: WorkerStrength) -> str:
    with_v, without_v, lift = aggregate(scores)
    mode = "live models" if live else f"simulated agents (worker: {strength.value})"

    lines = [
        "# Evaluation results",
        "",
        f"**Mode:** {mode}  ",
        f"**Contracts:** {len(scores)}  ",
        f"**Rule checks scored:** {with_v.total}",
        "",
    ]

    if not live:
        lines += [
            "> These numbers come from deterministic lexical stand-ins, not language",
            "> models. They characterise how the pipeline recovers from a shallow",
            "> reviewer's mistakes — the retrieval ladder, citation gate, and verdict",
            "> routing are all real code. They are **not** a model benchmark.",
            "",
        ]

    lines += [
        "## Absence claims (positive class = system says obligation not satisfied)",
        "",
        "| | Precision | Recall | F1 | FP (credibility) | FN (liability) |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| Workers only | {without_v.precision} | {without_v.recall} | {without_v.f1} "
        f"| {without_v.fp} | {without_v.fn} |",
        f"| **With verification** | **{with_v.precision}** | **{with_v.recall}** "
        f"| **{with_v.f1}** | **{with_v.fp}** | **{with_v.fn}** |",
        "",
        "## Verifier lift",
        "",
        f"- Findings overturned: **{lift.overturns}**",
        f"- Correct overturns (clause really was there): **{lift.overturns_correct}**",
        f"- Incorrect overturns (rescued a real gap): **{lift.overturns_incorrect}**",
        f"- Routed to human review: **{lift.needs_human}**",
        "",
    ]

    delta_fp = without_v.fp - with_v.fp
    if lift.overturns == 0:
        lines.append(
            "**The verifier overturned nothing.** On this set it is pure cost — "
            "either the workers made no recoverable errors, or the retrieval ladder "
            "failed to surface the clauses they missed."
        )
    else:
        lines.append(
            f"**The verifier eliminated {delta_fp} false absence claim(s)** "
            f"out of {without_v.fp} produced by the workers alone."
        )
        if lift.overturns_incorrect:
            lines.append(
                f" It also wrongly rescued {lift.overturns_incorrect} genuine gap(s), "
                "converting a correct finding into a missed liability."
            )
    lines.append("")

    lines += [
        "## Per contract",
        "",
        "| Contract | Checks | FP | FN | Overturns | What it tests |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in scores:
        lines.append(
            f"| {s.contract_id} | {s.with_verification.total} | {s.with_verification.fp} "
            f"| {s.with_verification.fn} | {s.lift.overturns} | {s.title} |"
        )
    lines.append("")

    errors = [
        d
        for s in scores
        for d in s.detail
        if d["outcome"] in ("FALSE_POSITIVE", "FALSE_NEGATIVE")
    ]
    if errors:
        lines += [
            "## Every error, itemised",
            "",
            "| Contract | Rule | Clause | Expected | Worker said | Final | Error |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in scores:
            for d in s.detail:
                if d["outcome"] in ("FALSE_POSITIVE", "FALSE_NEGATIVE"):
                    lines.append(
                        f"| {s.contract_id} | {d['rule_id']} | {d['clause']} "
                        f"| {d['expected']} | {d['worker_status']} | {d['final_status']} "
                        f"| {d['outcome']} |"
                    )
        lines.append("")

    unscored = [(s.contract_id, r) for s in scores for r in s.missing_findings]
    if unscored:
        lines += [
            "## Unscored (worker produced no finding)",
            "",
            *[f"- {cid}: {rid}" for cid, rid in unscored],
            "",
        ]

    return "\n".join(lines)


@app.command()
def main(
    rules: str = typer.Option("nda_sop.yaml", "--rules", "-r", help="SOP to evaluate against."),
    live: bool = typer.Option(False, "--live", help="Use real model clients (requires API keys)."),
    strength: WorkerStrength = typer.Option(
        WorkerStrength.NAIVE, "--strength", "-s", help="Simulated worker capability."
    ),
    out: Path | None = typer.Option(None, "--out", "-o", help="Results directory."),
) -> None:
    """Run the golden set and write results."""
    scores = asyncio.run(_run_all(rules, live=live, strength=strength))
    report = render_markdown(scores, live=live, strength=strength)
    print(report)

    with_v, without_v, lift = aggregate(scores)
    out_dir = out or RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "mode": "live" if live else "simulated",
                "worker_strength": strength.value,
                "sop": rules,
                "caveat": (
                    "Simulated mode uses deterministic lexical stand-ins, not language "
                    "models. These figures measure pipeline recovery behaviour, not "
                    "model accuracy."
                )
                if not live
                else None,
                "aggregate": {
                    "with_verification": with_v.as_dict(),
                    "without_verification": without_v.as_dict(),
                    "verifier_lift": lift.as_dict(),
                },
                "contracts": [s.as_dict() for s in scores],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nResults written to {path}")


if __name__ == "__main__":
    app()
