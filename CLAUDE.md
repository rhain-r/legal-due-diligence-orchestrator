# CLAUDE.md

Instructions for Claude Code working in this repository. Read before writing code.

## What this system is

A hierarchical multi-agent system that audits legal contracts against a firm's
compliance SOP. A **Lead Agent** plans and delegates, **Clause Workers** each own one
rule, a **Verifier** adversarially challenges every absence claim, and the reporter
emits a strict-JSON risk report.

The hard problem is **not** summarization. It is proving a clause is *absent*.
A false "missing clause" claim is the failure mode this whole architecture exists
to prevent. Design every decision against that.

## Non-negotiable rules

1. **No finding without a citation.** `PRESENT` and `NON_COMPLIANT` require at least
   one verified `Citation`. `MISSING` requires `SearchEvidence` and must carry zero
   citations. Enforced by validators in `agent/schemas.py` — do not weaken them.
2. **No LLM output is trusted as a dict.** Everything crossing an agent boundary goes
   through a Pydantic model. Validation failure is a retry that feeds the error back
   to the model; it is never a coerce.
3. **The Verifier must use a different retrieval strategy than the Worker.** Workers
   read semantically over assigned chunks; the verifier runs lexical/synonym/section
   retrieval over the whole document. Re-asking the same way is not verification.
4. **A verifier failure is never agreement.** Errors return `needs_human`.
5. **Never commit client documents.** `*.pdf` is git-ignored except for synthetic
   fixtures we authored ourselves.
6. **Determinism where possible.** Ingestion, citation checking, retrieval, and
   scoring are plain Python and unit-testable. Only reasoning goes to a model.
7. **Token cost is a design constraint.** Workers get only their assigned chunks.

## Repository shape — keep it this way

The root has exactly four subdirectories: `.claude/`, `agent/`, `assets/`, `docs/`,
plus `README.md`, `LICENSE`, `.gitignore`, `CLAUDE.md`, `pyproject.toml`. **Do not add
a fifth top-level directory** without asking — this constraint is deliberate. New
Python code goes under `agent/`, including tests and evals.

```
agent/
  schemas.py        message contracts between agents
  config.py         models, keys, limits, prompt loading
  llm.py            ModelClient protocol + provider adapters
  orchestrator.py   lead agent: plan, dispatch, route, trace
  workers.py        clause workers
  verifier.py       adversarial verification loop
  reporter.py       scoring and rendering
  sop.py            YAML rule loading
  ingestion/        parser.py, chunker.py     (no LLM calls)
  tools/            citation.py, search.py    (no LLM calls)
  prompts/          *.md system prompts
  rules/            *.yaml compliance SOPs
  tests/            pytest suite + fixtures/
```

## Stack

| Concern | Choice |
| --- | --- |
| Python | 3.12 pinned via `uv` (`requires-python >=3.10,<3.14`) |
| Reasoning | Anthropic Claude — planner and workers |
| Verification | Google Gemini — different lab on purpose |
| PDF parsing | `pypdf` (not the abandoned PyPDF2) |
| Validation | Pydantic v2, `extra="forbid"` |
| CLI | Typer + Rich |
| Test / lint | `pytest` (asyncio auto mode), `ruff` |

No agent framework. `agent/llm.py` defines a one-method `ModelClient` protocol; an
AutoGen or LangGraph adapter would be a single class. Keep that boundary clean.

## Commands

```bash
uv sync --extra dev
uv run pytest
uv run ruff check . --fix
uv run ldd inspect agent/tests/fixtures/sample_nda.pdf   # no API key needed
uv run ldd rules                                          # no API key needed
uv run ldd audit agent/tests/fixtures/sample_nda.pdf --markdown --verbose
```

If `uv sync` fails with a Python minor-version link error on Windows, pass the
interpreter explicitly — see `docs/setup-guide.md` § Troubleshooting.

## Conventions

- `from __future__ import annotations` at the top of every module. Type hints on
  every public function.
- System prompts live in `agent/prompts/*.md`, loaded via `config.load_prompt()`.
  They are the real logic of this system and belong in diffs, not string literals.
- Model names and numeric limits live only in `agent/config.py`.
- Tests run against `StubClient`. Never add a test that makes a real API call.
- Test the rejection paths, not just the happy path. A schema is only worth having
  if you have confirmed what it refuses.
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).

## Definition of done

- `uv run pytest` passes and covers the failure path.
- `uv run ruff check .` is clean.
- No new hardcoded model names outside `config.py`.
- No new top-level directory.
- If agent behavior changed, say so explicitly in the PR body.

## When you are unsure

Ask rather than guess on: compliance rule semantics, what counts as a "materially
equivalent" clause, and any change to the `Finding` or `VerificationResult`
validators. Those are domain decisions with legal consequences, not implementation
details.
