"""Command-line entry point.

    uv run ldd audit contract.pdf
    uv run ldd rules
    uv run ldd inspect contract.pdf
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agent.config import get_settings
from agent.reporter import render_terminal, write_json, write_markdown
from agent.sop import load_sop

app = typer.Typer(
    add_completion=False,
    help="Multi-agent contract due-diligence with adversarial verification.",
)
console = Console()


@app.command()
def audit(
    file: Path = typer.Argument(..., help="Path to the contract PDF."),
    rules: str = typer.Option("nda_sop.yaml", "--rules", "-r", help="SOP file in agent/rules/."),
    out: Path | None = typer.Option(None, "--out", "-o", help="Directory for report output."),
    markdown: bool = typer.Option(
        False, "--markdown", "-m", help="Also write a memo-style report."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Log agent activity."),
    simulate: bool = typer.Option(
        False,
        "--simulate",
        help="Run with deterministic stand-ins instead of models. No API key, no cost.",
    ),
) -> None:
    """Audit a contract against a compliance SOP."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)-8s %(name)s: %(message)s",
    )

    from agent.orchestrator import Orchestrator, run_audit  # deferred: keeps `ldd rules` fast

    settings = get_settings()

    if simulate:
        # Lets anyone clone the repo and see the pipeline run end to end. The
        # banner is deliberately loud: these findings are the output of lexical
        # heuristics, and reading them as model output would be a real mistake.
        from agent.evals.simulated import SimulatedVerifierClient, SimulatedWorkerClient

        console.print(
            "[black on yellow] SIMULATED RUN [/] no model calls; agents are "
            "deterministic stand-ins. Findings are not model output.\n"
        )
        rules_list = load_sop(rules).rules
        orchestrator = Orchestrator(
            settings,
            worker_client=SimulatedWorkerClient(rules_list),
            verifier_client=SimulatedVerifierClient(rules_list),
        )
        report = asyncio.run(orchestrator.audit(file, rules))
        render_terminal(report, console)
        out_dir = out or settings.report_dir
        console.print(f"\n[dim]JSON report:[/dim] {write_json(report, out_dir)}")
        if markdown:
            console.print(f"[dim]Markdown memo:[/dim] {write_markdown(report, out_dir)}")
        return

    if not settings.anthropic_api_key:
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/red] "
            "See [bold]docs/setup-guide.md[/bold] for the .env block."
        )
        raise typer.Exit(code=2)
    if not settings.has_verifier_credentials:
        console.print(
            "[yellow]Warning:[/yellow] no verifier credentials found. The cross-model "
            "check is the point of this system — set GOOGLE_API_KEY, or set "
            "verifier_provider=anthropic to accept a weaker same-provider check."
        )

    with console.status(f"Auditing {file.name}…", spinner="dots"):
        report = asyncio.run(run_audit(file, rules, settings=settings))

    render_terminal(report, console)

    out_dir = out or settings.report_dir
    json_path = write_json(report, out_dir)
    console.print(f"\n[dim]JSON report:[/dim] {json_path}")
    if markdown:
        console.print(f"[dim]Markdown memo:[/dim] {write_markdown(report, out_dir)}")


@app.command()
def rules(
    sop: str = typer.Option("nda_sop.yaml", "--sop", "-s", help="SOP file to display."),
) -> None:
    """Show the rules in a compliance SOP."""
    loaded = load_sop(sop)
    console.print(f"[bold]{loaded.name}[/bold] v{loaded.version} — {loaded.description}\n")

    table = Table(header_style="bold")
    table.add_column("Rule", style="dim", no_wrap=True)
    table.add_column("Clause")
    table.add_column("Domain", no_wrap=True)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Required", no_wrap=True)

    for rule in loaded.rules:
        table.add_row(
            rule.rule_id,
            rule.clause_name,
            rule.domain,
            rule.severity.value,
            "yes" if rule.required else "no",
        )
    console.print(table)


@app.command()
def inspect(
    file: Path = typer.Argument(..., help="Path to a contract PDF."),
) -> None:
    """Parse a contract and show its structure. No model calls, no API key needed.

    Useful for checking that citations will anchor correctly before spending
    tokens on an audit.
    """
    from agent.ingestion import chunk_blocks, parse_pdf
    from agent.tools.search import coverage_summary

    blocks = parse_pdf(file)
    chunks = chunk_blocks(blocks)
    stats = coverage_summary(blocks)

    console.print(
        f"[bold]{file.name}[/bold] — {stats['pages']} pages, {stats['blocks']} blocks, "
        f"{stats['sections']} sections, {len(chunks)} chunks\n"
    )

    table = Table(header_style="bold")
    table.add_column("Chunk", style="dim", no_wrap=True)
    table.add_column("Pages", no_wrap=True)
    table.add_column("Sections")
    table.add_column("Chars", justify="right")

    for chunk in chunks:
        table.add_row(
            chunk.chunk_id,
            f"{chunk.page_start}–{chunk.page_end}",
            ", ".join(chunk.section_refs[:6]) or "—",
            str(len(chunk.text)),
        )
    console.print(table)


if __name__ == "__main__":
    app()
