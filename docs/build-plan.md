# Build plan

How this system was built with Claude Code, phase by phase — and what's left.

Phases 0–8 are **done**; each entry records what shipped and the reasoning behind the
ordering, because the ordering is the part worth copying. Phases 9–10 are **open**,
with paste-ready prompts.

## Status

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Terminal ↔ GitHub wiring | ✅ done |
| 1 | Repo foundation, `uv`, lint, tests | ✅ done |
| 2 | Pydantic message contracts | ✅ done |
| 3 | Citation-anchored ingestion | ✅ done |
| 4 | Tools layer | ✅ done |
| 5 | Clause workers | ✅ done |
| 6 | Orchestrator | ✅ done |
| 7 | Verification loop | ✅ done |
| 8 | Reporting + CLI | ✅ done |
| 9 | Eval harness | ⬜ open |
| 10 | Portfolio polish | ⬜ open |

Current state: **65 tests passing**, `ruff` clean, CLI working end to end.

---

## The ordering, and why it's the interesting part

Phases 2–4 contain **zero LLM calls**. Schemas, PDF parsing, citation verification,
and retrieval are all deterministic, unit-tested Python. Agents don't appear until
Phase 5.

That's not fastidiousness. In a multi-agent system agents share *messages*, not
memory — so the schema is the architecture. Build agents first and each one invents
its own dict shape; the rest of the project becomes translation glue between four
incompatible payloads. Build the contract first and agents become interchangeable
implementations behind it, which is exactly why swapping `StubClient` for
`AnthropicClient` requires no changes anywhere else.

The second consequence: roughly two-thirds of this system is testable without an API
key. The full suite runs in under a second, for free.

---

## Phase 0 — Terminal ↔ GitHub

`gh` installed and authenticated, remote wired, branch pushed.

```bash
winget install --id GitHub.cli -e
```

```bash
gh auth login
```

GitHub.com → HTTPS → Yes → browser. That also installs a Git credential helper, so
`git push` stops prompting.

Inside a Claude Code session you can then just say *"open a PR for this branch"* —
it shells out to `gh`. There's no integration to install beyond the login.

## Phase 1 — Foundation

`pyproject.toml` with `uv`, Python pinned to 3.12, `ruff` at line-length 100 with
`E,F,I,UP,B,SIM,RUF`, `pytest` with `asyncio_mode = "auto"`.

**Pin the interpreter, don't fight it.** The dev machine runs Python 3.14, ahead of
what several dependencies support. `uv python pin 3.12` fetches its own CPython and
leaves the system install alone. `ruff`'s `target-version` is set to `py310` to match
`requires-python`'s lower bound, so lint never suggests syntax that breaks on 3.10.

## Phase 2 — Contracts (`agent/schemas.py`)

`Citation`, `TextBlock`, `Chunk`, `ComplianceRule`, `SearchEvidence`, `Finding`,
`VerificationResult`, `AuditReport`. All inherit `StrictModel` with `extra="forbid"`,
so a model inventing a field gets an error rather than a silently ignored
hallucination.

The two validators that carry the system's guarantees:

```python
status in (PRESENT, NON_COMPLIANT) and not citations  -> ValueError
status is MISSING and citations                       -> ValueError
status is MISSING and evidence is None                -> ValueError
verdict is OVERTURNED and not counter_citations       -> ValueError
```

Tests target the **rejection** paths. A schema is only worth having if you've
confirmed what it refuses.

## Phase 3 — Ingestion (`agent/ingestion/`)

`parse_pdf` → `TextBlock`s anchored to `(page, paragraph, section)`. Normalization
handles hyphenated line wraps, running headers repeated across pages, and
page-number-only lines. `chunk_blocks` never splits a paragraph and prefers section
boundaries.

**A citation is only as good as the page number that survived parsing.** Flatten a
contract into one blob, chunk at 1000 characters, and every downstream citation is a
plausible-looking guess.

One bug this phase produced, worth recording: `14 March 2025 (the "Effective
Date")...` parsed as *section 14*, and every following block inherited the bogus ref.
Fixed with a heading-length bound, plus a regression test. Real PDFs are adversarial
in boring ways.

## Phase 4 — Tools (`agent/tools/`)

`cite_source()` is the anti-hallucination gate: it verifies a quote appears in the
block before minting a `Citation`, with fuzzy matching at 0.90 for OCR drift (every
fuzzy match is logged). An agent can hallucinate a quote; it cannot hallucinate a
`Citation`.

`lexical_search`, `synonym_search`, and `section_scan` exist so the verifier has
retrieval mechanisms structurally different from the worker's semantic reading.

## Phase 5 — Workers (`agent/workers.py`)

One worker per rule, seeing only assigned chunks. Note how thin the module is —
the schema, citation gate, and tools do the load-bearing work.

The important behavior: a worker claiming `present` with a quote that fails
verification is **downgraded to `missing`**, not trusted. An unverifiable quote is
indistinguishable from a fabricated one, so it's treated as one.

## Phase 6 — Orchestrator (`agent/orchestrator.py`)

Plan → dispatch under a semaphore → route to verifier → assemble. Every step appends
to `runs/<audit_id>/trace.jsonl`.

Chunk assignment is deliberately generous: when no chunk matches a rule's terms, the
worker gets the whole document. A keyword miss is not evidence of absence, and
under-assigning manufactures exactly the false absence claims the system exists to
prevent.

A worker that raises is logged and skipped rather than sinking the audit.

## Phase 7 — Verification loop (`agent/verifier.py`)

The phase everything else was setup for. Three properties, all structural:

1. **Different retrieval strategy** — escalating ladder: synonym expansion → catch-all
   section scan → full-text pass, stopping at the first verifiable hit.
2. **Different model** — Gemini, while workers run on Claude.
3. **Inverted burden of proof** — the verifier tries to *find* the clause. One hit
   overturns.

The verifier is held to the worker's evidentiary standard: an overturn it can't quote
is rejected and the ladder continues. A verifier crash returns `needs_human` — failure
must never read as agreement.

The thesis test lives in `agent/tests/test_agents.py`: a contract where the cap on
damages is present but phrased so it shares no keywords with its own name. If that
test stops passing, the architecture no longer earns its cost.

## Phase 8 — Reporting + CLI (`agent/reporter.py`, `agent/__main__.py`)

Risk score computed in Python, not asked of a model — a scoring function can be
audited, explained to a client, and unit-tested. An LLM's "7.5" can be none of those.
Scores normalize against the rule set so different SOPs stay comparable.

Overturned findings are retained in an audit trail rather than deleted. Showing what
the system caught itself on is a feature.

CLI: `ldd audit`, `ldd rules`, `ldd inspect`. The last two need no API key.

---

## Phase 9 — Eval harness ⬜

**This is the highest-value remaining work.** Anyone can write "eliminates
hallucinations" in a README; almost nobody ships numbers. A reviewer who sees an eval
directory goes straight to it, and if it's honest, everything else gains credibility.

It's also the only way to know whether a prompt change helped.

### The prompt

```text
Build the eval harness. Keep everything inside agent/evals/ — the repo has a
deliberate four-folder root and I don't want a fifth.

- agent/evals/golden/: 5-6 synthetic contracts we author, each with a YAML answer
  key recording which clauses are genuinely present (with locations) and which were
  deliberately removed. Reuse the generator approach that produced
  agent/tests/fixtures/sample_nda.pdf. Include adversarial cases: a clause present
  but oddly worded, a clause that LOOKS present but is scoped out by an exception,
  and a genuinely absent one.
- agent/evals/run.py: runs the full pipeline over the golden set with StubClient
  optionally swapped for real clients. Report precision, recall, and F1 on MISSING
  claims, plus the two numbers that matter most in this domain, tracked separately:
    * false positives (claimed missing, actually present) — the credibility killer
    * false negatives (claimed present, actually missing) — the liability killer
- Report verifier lift: how many worker findings were overturned, and how many
  overturns were correct. That number is the entire justification for the
  architecture — if it's near zero, say so.
- Write results to agent/evals/results/<timestamp>.json and print a markdown table.

Then run it and put the real numbers in README.md, replacing the placeholder note.
```

**Done when:** you have numbers in the README. Publish them even if imperfect — an
honest 0.82 recall with a note on the failure mode reads as far more competent than an
unquantified claim of perfection.

## Phase 10 — Polish ⬜

### The prompt

```text
Final polish for a public portfolio repo:

- Record a terminal demo (asciinema or GIF) of a full audit, making sure the verifier
  overturn is visible. Save to assets/. That moment is the money shot.
- Update README with real eval numbers from Phase 9.
- Verify a cold clone works: fresh directory, uv sync, pytest, ldd inspect.
- Decide on CI. It needs .github/workflows/, which breaks the four-folder root rule —
  worth it or not is a judgement call, but an untested public repo is a weaker signal
  than a fifth directory.

Then run /code-review and /security-review over the whole repo.
```

---

## Claude Code workflow notes

| Move | When |
| --- | --- |
| `Shift+Tab` → plan mode | Start of every phase. Correct the plan, not the code. |
| `CLAUDE.md` | Rules you'd otherwise repeat. Edit it when you catch yourself repeating one. |
| `/clear` | Between phases. Stale context is worse than none. |
| `/code-review` | Before every PR. |
| `.claude/commands/*.md` | Any prompt typed three times. See `/audit` and `/new-rule`. |
| `claude -p "..."` | Headless one-shots, pipeable. |
| "open a PR for this branch" | Shells out to `gh`. |

**Three habits that matter more than any feature:**

1. **Commit at every green test.** Cheap checkpoints make it safe to attempt
   ambitious changes, because reverting costs nothing.
2. **Read the plan, skim the code.** Review attention is finite — spend it where
   decisions get made.
3. **When output is wrong twice, fix `CLAUDE.md`, not the prompt.** A prompt fix
   solves it once; a `CLAUDE.md` fix solves it for every future session.
