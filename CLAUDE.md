# CLAUDE.md

Instructions for Claude Code working in this repository. Read before writing code.

## What this system is

A hierarchical multi-agent system that audits legal contracts against a firm's
compliance SOP. A **Lead Agent** plans and delegates, **Worker Agents** each own one
clause domain, a **Verifier Agent** adversarially challenges every finding, and an
**Output Agent** emits a strict-JSON risk report.

The hard problem is **not** summarization. It is proving a clause is *absent*.
A false "missing clause" claim is the failure mode this whole architecture exists
to prevent. Design every decision against that.

## Non-negotiable rules

1. **No finding without a citation.** Every `Finding` carries `page`, `paragraph`,
   and the verbatim `quote` it was derived from. Findings of type `MISSING` carry
   the search evidence instead (terms tried, sections scanned).
2. **No LLM output is trusted as a dict.** Every agent-to-agent payload is parsed
   through a Pydantic model. Validation failure is a retry, never a coerce.
3. **The Verifier must use a different retrieval strategy than the Worker.** If the
   worker used semantic reasoning over chunks, the verifier does term/synonym
   expansion over raw text (and vice versa). Re-asking the same way is not verification.
4. **Never commit client documents.** `data/` and `*.pdf` are git-ignored. Test
   fixtures must be synthetic contracts we authored.
5. **Determinism where possible.** Chunking, citation anchoring, and report assembly
   are plain Python and unit-testable. Only reasoning is delegated to an LLM.
6. **Token cost is a design constraint.** Workers get only their assigned chunks,
   never the whole document.

## Stack

| Concern           | Choice                                        |
| ----------------- | --------------------------------------------- |
| Language          | Python 3.12 (pinned via `uv`; 3.14 is too new for AutoGen) |
| Agent framework   | Microsoft AutoGen (`autogen-agentchat` 0.4+)  |
| Reasoning         | Anthropic Claude (Sonnet 5) — primary          |
| Cross-check       | Google Gemini — independent verifier opinion   |
| PDF parsing       | `pypdf` (not the abandoned `PyPDF2`)           |
| Validation        | Pydantic v2, `model_config = {"extra": "forbid"}` |
| Package manager   | `uv`                                           |
| Test / lint       | `pytest`, `ruff`                               |

## Layout

```
agents/        orchestrator.py, workers.py, verifier.py, reporter.py
core/          schemas.py (Pydantic contracts), config.py
ingestion/     parser.py (PDF -> anchored blocks), chunker.py
tools/         citation.py (cite_source), search.py (keyword/synonym retrieval)
rules/         *.yaml compliance SOPs
evals/         golden contracts + scoring harness
tests/         unit tests; fixtures/ holds synthetic PDFs
docs/          architecture.md, compliance-rules.md, build-plan.md
```

## Commands

```bash
uv sync                      # install deps
uv run pytest -q             # tests
uv run ruff check . --fix    # lint
uv run python -m agents.orchestrator --file tests/fixtures/nda_sample.pdf
uv run python -m evals.run   # scoring harness (precision/recall on golden set)
```

## Conventions

- Type hints on every public function. `from __future__ import annotations` at top.
- Agent system prompts live in `agents/prompts/*.md`, not inline strings — they are
  the real logic of this system and deserve to be diffable.
- Log every agent turn to `runs/<audit_id>/trace.jsonl`. The audit trail is a
  product feature, not debug output.
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
- One phase from `docs/build-plan.md` per branch, per PR.

## Definition of done for any phase

- Unit tests pass and cover the failure path, not just the happy path.
- `ruff check .` is clean.
- No new hardcoded model names outside `core/config.py`.
- If agent behavior changed, `evals/` was re-run and the numbers are in the PR body.

## When you are unsure

Prefer asking over guessing on: compliance rule semantics, what counts as a
"materially equivalent" clause, and any change to the `Finding` schema. Those are
domain decisions with legal consequences, not implementation details.
