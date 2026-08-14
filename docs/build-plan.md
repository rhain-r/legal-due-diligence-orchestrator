# Build Plan — Legal Due Diligence Orchestrator

A phase-by-phase tutorial for building this system with Claude Code, from an empty
folder to a repo that survives a senior engineer opening it.

## How to use this document

Each phase has the same four parts:

1. **Goal** — what exists at the end that didn't exist at the start.
2. **Why this order** — the reasoning. Skip this and you'll be tempted to reorder,
   and the reordering is where these projects die.
3. **The prompt** — paste it into Claude Code verbatim. It's written to be pasted.
4. **Done when** — the check that lets you move on.

**One phase = one branch = one PR.** That rule is doing more work than it looks like:
it makes your commit history readable to anyone evaluating the repo, and it keeps each
Claude Code session's context scoped to one problem.

### The two-mode habit

The single biggest quality difference in Claude Code output comes from this:

- **Plan mode first** (`Shift+Tab` until the prompt shows plan mode) — Claude reads,
  researches, and proposes an approach without editing anything. You correct the plan
  when it's cheap to correct.
- **Then let it build.** Approving a plan is where you spend your judgment. Reviewing
  400 lines of already-written code is where you spend your patience.

Every phase below assumes you start in plan mode.

---

## Phase 0 — Wire the terminal to GitHub

**Goal:** `git` and `gh` work from your terminal, Claude Code can push branches and
open PRs on your behalf, and this repo is connected to your GitHub remote.

**Why this order:** Every later phase ends with "open a PR." If that's manual
clicking in a browser, you'll stop doing it by Phase 3 and the commit history — the
part reviewers actually read — turns into one giant `initial commit`.

### 0.1 Install the GitHub CLI

```bash
winget install --id GitHub.cli -e
```

Close and reopen your terminal afterward so `gh` lands on your `PATH`.

### 0.2 Authenticate

```bash
gh auth login
```

Answer: **GitHub.com** → **HTTPS** → **Yes** (authenticate Git with your GitHub
credentials) → **Login with a web browser**. Copy the one-time code, paste it in the
browser, done. This also installs a Git credential helper, so `git push` stops asking
for passwords forever.

Verify:

```bash
gh auth status
```

### 0.3 Confirm the remote

Already configured for you:

```bash
git remote -v
```

You should see `https://github.com/rhain-r/legal-due-diligence-orchestrator.git`
for both `fetch` and `push`.

### 0.4 First push

```bash
git add -A
```

```bash
git commit -m "chore: repo foundation, CLAUDE.md, and build plan"
```

```bash
git push -u origin main
```

If GitHub rejects it because the remote already has commits (e.g. a README created
in the web UI), reconcile once with `git pull --rebase origin main` and push again.

### 0.5 What you can now do from the terminal

| Command | What it does |
| --- | --- |
| `claude` | Start an interactive session in this repo |
| `claude -p "summarize the diff"` | One-shot headless run, prints and exits |
| `gh pr create --fill` | Open a PR from the current branch |
| `gh pr view --web` | Open the current PR in a browser |
| `gh pr checks` | Watch CI without leaving the terminal |
| `gh issue create -t "..." -b "..."` | File an issue |

Inside a Claude Code session, you can just say *"open a PR for this branch"* — it
shells out to `gh` for you. That's the whole "connect Claude and GitHub" story;
there's no integration to install beyond `gh auth login`.

**Done when:** `gh auth status` shows you logged in, and your first commit is visible
on github.com.

---

## Phase 1 — Repo foundation

**Goal:** Python 3.12 environment, dependencies, lint/test tooling, CI.

**Why this order:** `CLAUDE.md` already exists (see the repo root) and it's the
highest-leverage file here — it's loaded into context automatically at the start of
every session, so every rule in it is a rule you never have to repeat. What's missing
is the runnable environment underneath it.

> **Version note:** your system Python is 3.14.7. AutoGen targets 3.10–3.13. Don't
> fight this — `uv` will fetch and pin 3.12 for this project without touching your
> system install.

### The prompt

```text
Set up the Python project foundation. Requirements:

- uv-managed project pinned to Python 3.12 (my system python is 3.14, which AutoGen
  doesn't support yet). Create .python-version and pyproject.toml.
- Dependencies: autogen-agentchat, autogen-ext[anthropic,openai], anthropic,
  google-genai, pypdf, pydantic>=2, pyyaml, python-dotenv, typer, rich.
- Dev dependencies: pytest, pytest-cov, ruff.
- Configure ruff in pyproject.toml: line-length 100, select E,F,I,UP,B.
- Create the package layout from CLAUDE.md (agents/, core/, ingestion/, tools/,
  rules/, evals/, tests/) with __init__.py files and .gitkeep in empty dirs.
- core/config.py: pydantic-settings Settings class reading .env. All model names and
  runtime limits live here — nowhere else in the codebase.
- One smoke test: tests/test_config.py asserts Settings loads from .env.example values.
- .github/workflows/ci.yml: on push and PR, run uv sync, ruff check, pytest.

Then run uv sync and the test suite and show me the output.
```

**Done when:** `uv run pytest -q` passes and `uv run ruff check .` is clean.

**Ship it:**

```bash
git checkout -b phase-1-foundation
```

```bash
gh pr create --fill --title "feat: project foundation and CI"
```

---

## Phase 2 — Contracts first (the Pydantic schemas)

**Goal:** `core/schemas.py` — the data model every agent speaks.

**Why this order — this is the phase people skip, and it's the one that matters most.**
In a multi-agent system the schema *is* the architecture. Agents don't share memory;
they share messages. If you write agents first, each one invents its own dict shape
and you spend the rest of the project writing translation glue. Define the contract
first and the agents become interchangeable implementations behind it.

Also: this is the file you'll hand to a reviewer when they ask "how does this actually
work?" A well-designed `schemas.py` answers that faster than a diagram.

### The prompt

```text
Read CLAUDE.md, then design core/schemas.py — the message contracts between agents.
Use Pydantic v2, model_config = ConfigDict(extra="forbid"), full type hints.

Model these:

- Citation: page:int, paragraph:int, quote:str (verbatim, max ~300 chars).
- FindingStatus: enum PRESENT | MISSING | AMBIGUOUS | NON_COMPLIANT.
- SearchEvidence: what a worker actually did to justify an absence claim —
  terms_searched:list[str], sections_scanned:list[str], strategy:Literal["semantic","lexical","synonym"].
- Finding: id, contract_id, rule_id, agent_name, status, rationale,
  citations:list[Citation], evidence:SearchEvidence|None, confidence:float 0-1.
  Add a model_validator: status=PRESENT or NON_COMPLIANT requires >=1 citation;
  status=MISSING requires evidence and must have zero citations.
- VerificationResult: finding_id, verdict enum CONFIRMED|OVERTURNED|NEEDS_HUMAN,
  verifier_strategy, counter_citations:list[Citation], reasoning.
- ComplianceRule: rule_id, clause_name, domain, description,
  synonyms:list[str], severity enum, required:bool.
- AuditReport: audit_id, contract_id, generated_at, findings, verifications,
  risk_score, unresolved:list[str].

Write tests/test_schemas.py covering the validator failure paths specifically:
a MISSING finding with citations must raise; a PRESENT finding without citations
must raise. Don't only test the happy path.
```

**Done when:** the invalid-construction tests fail loudly. If a `MISSING` finding
with citations attached constructs successfully, the schema isn't doing its job.

---

## Phase 3 — Citation-anchored ingestion

**Goal:** `ingestion/parser.py` + `ingestion/chunker.py` — PDF in, text blocks out,
each block carrying the `(page, paragraph)` it came from.

**Why this order:** `cite_source()` can only return a real page number if the page
number survived parsing. Almost every "AI contract tool" demo breaks here — text gets
flattened into one blob, chunked at 1000 characters, and the citation becomes a
plausible-looking guess. Anchor first, and every downstream citation is free.

### The prompt

```text
Build the ingestion layer. Two modules, both pure Python — no LLM calls anywhere here,
because this must be deterministic and unit-testable.

ingestion/parser.py:
- parse_pdf(path) -> list[TextBlock] using pypdf.
- TextBlock (add to core/schemas.py): page:int, paragraph:int, text:str, char_start:int.
- Split pages into paragraphs on blank lines, but first normalize the junk real
  contracts contain: hyphenated line-wraps ("indemnifi-\ncation"), running
  headers/footers repeated on every page, and page-number-only lines.
- Detect section headings (e.g. "7.1 Limitation of Liability", "ARTICLE IV") and
  attach section_ref to each block so citations can say "§7.1" not just "page 12".

ingestion/chunker.py:
- chunk_blocks(blocks, max_tokens, overlap) -> list[Chunk] where Chunk holds the
  blocks it contains. NEVER split mid-paragraph. A chunk knows its page range and
  section refs.
- Chunks are what workers receive, so this is the unit of delegation.

tests/: build a small synthetic contract PDF fixture programmatically (reportlab or
a checked-in minimal PDF) with known text on known pages. Assert that a phrase on
page 3 paragraph 2 round-trips to exactly (3, 2). Test the hyphenation and
repeated-header cleanup explicitly.
```

**Done when:** a phrase you plant on page 3 comes back anchored to page 3. Test it
with a multi-page fixture — single-page tests pass for the wrong reasons.

---

## Phase 4 — The tools layer

**Goal:** `tools/citation.py` and `tools/search.py` — the functions agents are allowed
to call.

**Why this order:** Agents are only as good as their tools, and tools are ordinary
functions you can test without spending a token. Build and test them standalone, then
register them with the framework. Debugging a broken tool through three layers of agent
conversation is miserable; debugging it in a unit test takes seconds.

### The prompt

```text
Build tools/ — plain functions with docstrings written for an LLM to read, since the
docstring becomes the tool description the model sees.

tools/citation.py:
- cite_source(chunk_id, quote) -> Citation. Verifies the quote actually appears in
  that chunk (normalized whitespace, case-insensitive) and raises CitationError if
  not. This is the anti-hallucination gate: an agent literally cannot cite text
  that isn't there.
- Include fuzzy matching (difflib) with a similarity floor of 0.9 so minor
  whitespace/OCR drift doesn't reject a legitimate quote — but log every fuzzy match.

tools/search.py:
- lexical_search(blocks, terms) -> list[TextBlock] — exact/stemmed term hits.
- synonym_search(blocks, rule) -> list[TextBlock] — expands using
  ComplianceRule.synonyms plus common legal phrasings.
- section_scan(blocks, heading_pattern) -> list[TextBlock].
These three exist so the Verifier has retrieval strategies structurally different
from the Worker's semantic reading. That difference is the point.

Full unit tests, no LLM in the loop.
```

**Done when:** `cite_source()` raises on a fabricated quote. Write that test first.

---

## Phase 5 — Worker agents

**Goal:** `agents/workers.py` — one agent per clause domain, each returning validated
`Finding` objects.

**Why now:** schema, ingestion, and tools are all done and tested. The worker is
now a thin thing: prompt + tools + output parsing. That's how it should feel. If
writing a worker feels hard, something below it is missing.

### The prompt

```text
Build agents/workers.py using AutoGen (autogen-agentchat 0.4 API — check the
installed version's actual API before writing, don't assume the 0.2 syntax).

- ClauseWorker: configured with a ComplianceRule, receives only its assigned chunks,
  has access to cite_source and lexical_search.
- System prompts go in agents/prompts/worker.md, loaded at runtime — not inline strings.
  The prompt must instruct: reason about legal meaning, not keywords; a renamed clause
  that does the same work counts as PRESENT; when claiming MISSING, report exactly
  which terms and sections you checked.
- Output is parsed into Finding. On ValidationError, retry up to 2x feeding the
  validation error back to the model, then raise. Never coerce invalid output.
- Factory: build_workers(rules, chunks) -> list[ClauseWorker], grouping rules by domain
  so one worker owns liability, another termination, etc.

Tests use a stubbed model client returning canned JSON — real API calls in unit tests
make the suite slow, flaky, and expensive. Cover: valid output, malformed JSON that
recovers on retry, and malformed output that exhausts retries.
```

**Done when:** workers produce validated `Finding`s against a fixture contract with a
mocked client, and the retry path is tested.

---

## Phase 6 — The Orchestrator

**Goal:** `agents/orchestrator.py` — loads the SOP, plans, dispatches, collects.

**Why now:** it's the conductor. It needs the players to exist first.

### The prompt

```text
Build agents/orchestrator.py — the Lead Agent.

Flow:
1. Ingest the PDF, load a ComplianceRule set from rules/*.yaml.
2. Planning step: an LLM call that maps rules to clause domains and decides which
   chunks each worker gets — using section headings, so the liability worker gets the
   liability sections rather than all 40 chunks. Persist the plan to the trace.
3. Dispatch workers concurrently with asyncio.gather, bounded by a semaphore.
4. Collect Findings. Route every MISSING and every confidence < 0.7 to the Verifier
   (Phase 7 — stub the call for now with a typed interface).
5. Enforce MAX_AGENT_TURNS from config as a hard ceiling. An unbounded agent loop is
   an unbounded bill.
6. Write runs/<audit_id>/trace.jsonl — every dispatch, every finding, every timing.

Also add rules/nda_sop.yaml: 6-8 real NDA compliance rules (confidentiality
definition, term, permitted disclosures, return/destruction of materials, governing
law, cap on damages, injunctive relief) with synonyms and severity.

Typer CLI entry point: --file, --rules, --out.
```

**Done when:** `uv run python -m agents.orchestrator --file <fixture>` runs end to end
and writes a trace file, even with the verifier stubbed.

---

## Phase 7 — The Verification Loop

**Goal:** `agents/verifier.py`. **This is the phase the whole project exists for.**

**Why now:** you can only challenge findings that exist. Everything before this was
setup for this phase.

Three rules make verification real rather than theatrical:

1. **Different strategy.** The worker read semantically; the verifier runs synonym
   expansion and section scans over raw text. Asking the same model the same question
   the same way gets you the same answer, confidently.
2. **Different model.** Route the verifier to Gemini. Two models from different
   labs converging on "this clause is absent" is real evidence. One model agreeing
   with itself is not.
3. **Burden of proof inverts.** The verifier's job is to *find the clause*, not to
   confirm it's missing. One hit overturns the finding.

### The prompt

```text
Build agents/verifier.py — the adversarial verification loop. Read CLAUDE.md rule 3
first; it constrains this design.

VerifierAgent.challenge(finding, blocks) -> VerificationResult:

- For MISSING findings, run an escalating ladder and stop at the first hit:
    1. synonym_search using the rule's synonyms
    2. section_scan for headings semantically near the clause name
    3. an LLM pass over the FULL document text with a single narrow question:
       "Does any language here create the obligation described? Quote it or answer NONE."
- The verifier is prompted adversarially: its objective is to PROVE THE WORKER WRONG.
  System prompt in agents/prompts/verifier.md.
- Route this agent to Gemini via core/config.py while workers stay on Claude, so the
  cross-model check is real and not two calls to the same model.
- Any hit -> OVERTURNED with counter_citations. Ladder exhausted -> CONFIRMED with the
  full SearchEvidence attached. Contradictory or low-confidence -> NEEDS_HUMAN.
  Never silently drop a disagreement — NEEDS_HUMAN is a legitimate, valuable outcome.
- Cap verification at 3 strategies per finding.

Then wire the real verifier into the orchestrator, replacing the Phase 6 stub.

Tests: a fixture contract where liability IS present but phrased unusually
("Neither party's aggregate obligation shall exceed..."). A naive keyword worker
misses it; the verifier must overturn. That test is this project's thesis statement —
make it a good one.
```

**Done when:** the overturn test passes. A verifier that never overturns anything is
a verifier that isn't running.

---

## Phase 8 — Output Agent and report

**Goal:** `agents/reporter.py` — validated JSON report plus a human-readable summary.

### The prompt

```text
Build agents/reporter.py.

- Assemble AuditReport from findings + verifications. Report only findings that
  survived verification; keep OVERTURNED ones in an audit_trail section rather than
  deleting them — showing what the system caught itself on is a feature.
- risk_score: deterministic Python from rule severity and finding status. Do NOT ask
  an LLM to produce a number; a scoring function is auditable and an LLM's 7.5 is not.
- Emit reports/<audit_id>.json (strict schema) and a Rich terminal table.
- Optional --markdown flag for a memo-style summary a lawyer would actually read:
  what's missing, why it matters, where to look.
```

**Done when:** the JSON round-trips through `AuditReport.model_validate_json()`.

---

## Phase 9 — The eval harness

**Goal:** `evals/` — precision and recall against contracts with known planted omissions.

**Why this phase is the real portfolio differentiator:** anyone can write "eliminates
hallucinations" in a README. Almost nobody ships numbers. A reviewer who sees
`evals/` skips straight to it, and if it's honest, everything else in the repo gains
credibility. It's also the only way *you* will know whether a prompt change helped.

### The prompt

```text
Build evals/.

- evals/golden/: 5-6 synthetic contracts we author, each with a YAML answer key
  listing which clauses are genuinely present (with locations) and which were
  deliberately removed. Include adversarial cases: a clause present but oddly worded,
  a clause that LOOKS present but is scoped out by an exception, a genuinely absent one.
- evals/run.py: runs the full pipeline over the golden set and reports
  precision, recall, F1 on MISSING claims — plus the two numbers that matter most
  in this domain, tracked separately:
    * false positives (claimed missing, actually present) — the credibility killer
    * false negatives (claimed present, actually missing) — the liability killer
- Report verifier lift: how many worker findings were overturned, and how many
  overturns were correct. That number justifies the entire architecture.
- Output a markdown table, and write results to evals/results/<timestamp>.json so
  you can track drift as prompts change.
```

**Done when:** you have real numbers. Put them in the README **even if they're
imperfect** — an honest 0.82 recall with a note on the failure mode reads as far more
competent than an unquantified claim of perfection.

---

## Phase 10 — Portfolio polish

**Goal:** the repo reads well to someone who spends 90 seconds on it.

### The prompt

```text
Polish pass for a public portfolio repo:

- docs/architecture.md: agent topology, message contracts, sequence of a full audit,
  and an honest "limitations and failure modes" section.
- docs/compliance-rules.md: the YAML rule format, with a worked example of authoring
  a new rule.
- Update README with real eval numbers from evals/results/.
- Record a terminal demo (asciinema or a GIF) of a full audit run — including the
  moment the verifier overturns a finding. That's the money shot; make sure it's
  visible in the recording.
- Add .claude/commands/ with two custom slash commands: /audit (run pipeline on a
  fixture and summarize) and /new-rule (scaffold a compliance rule + test).
- Verify a cold clone works: fresh directory, uv sync, pytest. Fix whatever breaks.
```

Then run `/code-review` and `/security-review` over the whole thing before you tell
anyone about it.

---

## Claude Code workflow cheatsheet

| Move | When to use it |
| --- | --- |
| `Shift+Tab` → plan mode | Start of every phase. Correct the plan, not the code. |
| `CLAUDE.md` | Rules you'd otherwise repeat every session. Edit it when you catch yourself repeating something. |
| `/init` | Regenerate `CLAUDE.md` once real code exists — it'll pick up actual conventions. |
| `/clear` | Between phases. Stale context is worse than no context. |
| `/code-review` | Before every PR. |
| `.claude/commands/*.md` | Any prompt you've typed three times. |
| `.claude/agents/*.md` | Subagents for scoped work (e.g. a test-writer) — keeps the main context clean. |
| `claude -p "..."` | Headless one-shots, pipeable into scripts. |
| "open a PR for this branch" | Shells out to `gh`. No integration needed beyond `gh auth login`. |

### Three habits that matter more than any feature

1. **Commit at every green test.** Cheap checkpoints make it safe to let Claude try
   something ambitious, because reverting costs nothing.
2. **Read the plan, skim the code.** Your review attention is finite. Spend it where
   decisions get made.
3. **When output is wrong twice, fix `CLAUDE.md` — not the prompt.** A prompt fix
   solves it once. A `CLAUDE.md` fix solves it for every future session.

---

## Suggested pace

| Sessions | Phases | Notes |
| --- | --- | --- |
| 1 | 0–1 | Setup. Mostly mechanical. |
| 2–3 | 2–4 | Schemas, ingestion, tools. No LLM calls yet — pure, testable Python. |
| 4–5 | 5–6 | Workers and orchestration. First real agent runs. |
| 6–7 | 7 | The verifier. Budget the most time here; it's the hardest and most valuable. |
| 8 | 8–9 | Report and evals. |
| 9 | 10 | Polish. |

If you only get halfway, stop after Phase 7. A repo with ingestion, workers, and a
working verification loop — properly tested — is a stronger portfolio piece than all
ten phases done shallowly.
