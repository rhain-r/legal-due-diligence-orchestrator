<h1 align="center">Legal Due Diligence Orchestrator</h1>

<p align="center">
  <strong>A multi-agent AI system that audits legal contracts against a firm's compliance SOP — then argues with itself to make sure it's right.</strong>
</p>

<p align="center">
  <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10--3.13-3776AB?logo=python&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/reasoning-Claude%20Sonnet-D97757">
  <img alt="Gemini" src="https://img.shields.io/badge/verification-Gemini-4285F4?logo=google&logoColor=white">
  <img alt="Pydantic v2" src="https://img.shields.io/badge/validation-Pydantic%20v2-E92063">
  <img alt="Tests" src="https://img.shields.io/badge/tests-85%20passing-2ea043">
  <img alt="Evaluated" src="https://img.shields.io/badge/eval-6%20golden%20contracts-8957e5">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-blue">
</p>

---
## Why This Matters:
* **Eliminates False Negatives:** Prevents the most dangerous failure mode in AI contract review—quietly missing missing clauses.
* **Reduces Paralegal Load:** Automates the tedious "absence-checking" phase of legal due diligence.
* **Auditable & Deterministic:** Every AI decision is backed by schema-enforced citations and deterministic Python scoring.

---
## The problem

Contract review tools are good at telling you what a document **says**. The expensive
paralegal work is proving what a document **doesn't** say — that there's no cap on
damages, no governing-law clause, no return-of-materials obligation.

That's also where language models fail hardest, and fail *quietly*. A model that skims
a 90-page master services agreement and reports *"no limitation of liability found"*
produces output identical to a model that looked carefully and found nothing. Nothing
in the response distinguishes diligence from laziness — and in legal work that false
negative is the difference between a clean deal and uncapped exposure.

**So this system treats absence claims as untrusted by default.** Any agent that
reports a missing clause triggers a verifier that re-reads the document with a
deliberately *different* retrieval strategy, on a *different* model, with the burden
of proof inverted — before the finding is allowed into the report.

## The loop, doing its job

![Verification loop recovering eight clauses](assets/demo.svg)

Reproduce it yourself — no API key required:

```bash
uv run ldd audit agent/evals/golden/build/msa_buried.pdf --simulate --verbose
```

## Architecture

![Agent architecture](assets/architecture.svg)

<details>
<summary>Text version</summary>

```
[ Ingestion ]  pypdf → paragraphs anchored to (page, ¶, §)
      │
      ▼
[ Lead Agent ]  loads SOP, scopes each rule to relevant sections
      │
      ├──► [ Liability Worker ]     ──► "uncapped risk"
      ├──► [ Termination Worker ]   ──► "clause missing"
      ├──► [ Jurisdiction Worker ]  ──► "found, §8"
      │
      ▼
[ Verifier ]  synonym search → section scan → full text
      │        goal: PROVE THE WORKER WRONG
      ├──► one verifiable hit ⇒ finding overturned
      │
      ▼
[ Output Agent ]  Pydantic-validated JSON + risk score
```

</details>

## Engineering Challenges Solved

Building autonomous agents for legal tech requires overcoming severe LLM limitations. Here is how this system handles them:

* **The "Lazy LLM" Problem:** A model skimming a 90-page MSA will often say "no clause found" just to save compute. 
  * *Solution:* **Adversarial Verification.** The verifier is forced to use a different retrieval strategy (synonym search + section scans) and a different model (Gemini vs. Claude), with the burden of proof inverted.
* **Hallucinated Quotes:** LLMs notoriously invent text that sounds legally plausible.
  * *Solution:* **Citation Gates.** A custom `cite_source()` function verifies quotes against the anchored `(page, ¶, §)` source text before minting a Citation object. 
* **Self-Contradictory JSON:** Agents often output a status of "MISSING" while providing a quote of the clause.
  * *Solution:* **Schema-Enforced Integrity.** Pydantic v2 with `extra="forbid"` throws a `ValidationError` if an agent submits logically impossible combinations.

## Quick start

**Prerequisites:**
* [uv](https://docs.astral.sh/uv/) installed on your machine.
* API Keys for Anthropic and Google Gemini (for the full audit).

```bash
git clone [https://github.com/rhain-r/legal-due-diligence-orchestrator.git](https://github.com/rhain-r/legal-due-diligence-orchestrator.git)
cd legal-due-diligence-orchestrator
uv sync
```

`uv` fetches its own CPython 3.12 — your system Python is untouched.

**Try it with no API key.** `inspect` parses a contract and shows its structure:

```bash
uv run ldd inspect agent/tests/fixtures/sample_nda.pdf
```

```
sample_nda.pdf — 3 pages, 63 blocks, 9 sections, 1 chunks
┌───────┬───────┬──────────────────┬───────┐
│ Chunk │ Pages │ Sections         │ Chars │
├───────┼───────┼──────────────────┼───────┤
│ c000  │ 1–3   │ 1, 2, 3, 4, 5, 6 │  3968 │
└───────┴───────┴──────────────────┴───────┘
```

Then add keys to `.env` (see [setup guide](docs/setup-guide.md)) and run a full audit:

```bash
uv run ldd audit agent/tests/fixtures/sample_nda.pdf --markdown --verbose
```

The bundled synthetic NDA is built to demonstrate the loop: its **cap on damages is
present but buried in "General Provisions"** and worded without the words *cap*,
*damages*, or *limitation of liability*. Expect a worker to report it missing and the
verifier to overturn that. Return-of-materials and injunctive relief are genuinely
absent and should survive as confirmed gaps.

## Repository layout

```
agent/
├── schemas.py         message contracts — the architecture lives here
├── config.py          models, keys, limits; nothing hardcoded elsewhere
├── llm.py             provider adapters + structured output with retry
├── orchestrator.py    plan → dispatch → route → trace
├── workers.py         one clause domain each
├── verifier.py        the adversarial loop
├── reporter.py        scoring, JSON, terminal, markdown
├── sop.py             YAML rule loading
├── ingestion/         PDF → anchored blocks → chunks   (no LLM calls)
├── tools/             cite_source(), retrieval strategies (no LLM calls)
├── prompts/           system prompts, on disk so they show up in diffs
├── rules/             compliance SOPs as YAML
├── evals/             golden contracts, answer keys, scoring harness
└── tests/             85 tests, all against stubbed clients
assets/                architecture diagram
docs/                  architecture · compliance-rules · setup-guide · build-plan
```

Roughly two-thirds of the system is deterministic Python. Everything that *can* be a
tested function instead of a prompt, is one — which is why the whole suite runs in
under a second with no API key and no cost.

## Evaluation

Six synthetic contracts, 48 rule checks, each with a YAML answer key recording which
obligations are genuinely present and which were deliberately removed. The set
includes the two traps that matter: clauses **present but renamed**, and clauses that
**look present but are negated by their own wording**.

```bash
uv run python -m agent.evals.run
```

> **What these numbers are.** No API keys were used. The agents are deterministic
> lexical stand-ins, so this measures **pipeline recovery behaviour** — the retrieval
> ladder, citation gate, and verdict routing, all real code — and **not** model
> accuracy. Swapping in Claude and Gemini would produce different numbers, and those
> would be the ones worth quoting about models. The stand-ins never read an answer key.

Positive class is an absence claim, so a false positive is *"we told the client their
cap on damages is missing when it wasn't"*.

| Worker | | Precision | Recall | F1 | FP | FN |
| --- | --- | --- | --- | --- | --- | --- |
| Keyword-blind | workers only | 0.222 | 0.667 | 0.333 | 21 | 3 |
| Keyword-blind | **+ verification** | **0.462** | **0.667** | **0.546** | **7** | **3** |
| Synonym-aware | workers only | 0.417 | 0.556 | 0.477 | 7 | 4 |
| Synonym-aware | + verification | 0.417 | 0.556 | 0.477 | 7 | 4 |

**21 overturns, 21 correct, 0 incorrect.** The verifier never once rescued a gap that
was genuinely there — the failure mode that would make verification worse than useless.

### What the eval actually found

**1. Verifier lift is inversely proportional to synonym quality.** Against a
keyword-blind worker it eliminated 14 of 21 false absence claims. Against a
synonym-aware worker it eliminated **zero**, because the worker had already caught
them. Actionable conclusion: *invest in the SOP's synonym lists first.* Verification
is the safety net for what synonyms miss, not a substitute for writing them well.

**2. All 7 remaining false positives are on one contract** — the one whose every
clause is renamed ("Protected Material" for Confidential Information, "Applicable
Regime" for Governing Law). A lexical verifier cannot bridge that gap. **This is
precisely the work a real model does**, and it's the clearest evidence here of where
the simulation's ceiling sits.

**3. Every false negative is a false-*presence* claim the verifier never saw.**
By design it challenges absence claims only, so a worker that confidently matches a
reassuring heading — over a clause that negates itself — is never contradicted. That
is the architecture's real structural blind spot, and it now has a number on it.
Symmetric verification of presence claims is the highest-value next change.

Full breakdown, including every error itemised: [`agent/evals/`](agent/evals/).
Raw results: [`agent/evals/results/`](agent/evals/results/).

## Testing

```bash
uv run pytest
```

```
85 passed in 1.10s
```

The suite runs entirely against `StubClient`. Tests target rejection paths, not just
happy paths: fabricated quotes, `MISSING` findings carrying citations, verifier
overturns it can't quote, and verifier crashes that must not read as agreement.

The load-bearing test is `test_verifier_overturns_a_false_absence_claim` — a contract
where the clause is present but shares no keywords with its own name. If that test
stops passing, the architecture no longer earns its cost.

## Tech stack

| Component | Choice | Why |
| --- | --- | --- |
| Reasoning | Anthropic Claude Sonnet | Planner and clause workers |
| Verification | Google Gemini | Different lab, so the cross-check is real |
| Parsing | `pypdf` | Actively maintained, unlike PyPDF2 |
| Validation | Pydantic v2 | `extra="forbid"` everywhere |
| Orchestration | Purpose-built `asyncio` | See below |
| Tooling | `uv`, `pytest`, `ruff`, `typer`, `rich` | |
| Built with | Claude Code | See [build plan](docs/build-plan.md) |

**On agent frameworks.** The orchestration here is purpose-built rather than delegated
to AutoGen or LangGraph. `agent/llm.py` defines a one-method `ModelClient` protocol,
so an adapter for any framework is a single class — nothing in schemas, ingestion,
tools, or reporting moves. The delegation logic is ~40 lines of `asyncio.gather` under
a semaphore; a framework wouldn't have made that shorter, and would have made the
verification ladder harder to express. It also keeps the test suite free and offline.

## Status and honest limitations

**Working:** ingestion, tools, workers, orchestrator, verification loop, reporting,
CLI, eval harness. 85 tests passing, `ruff` clean.

**Never measured against real models.** Every number above comes from deterministic
stand-ins. The system is wired for Claude and Gemini and will run against them, but
it has not been, so no claim about model accuracy appears anywhere in this repo.

**The verifier only challenges absence claims.** False-presence claims — a clause that
looks present under a matching heading but is negated in its body — pass straight
through. Quantified above; fixing it is the top of the backlog.

Other known limits, in full: [architecture.md § Known limitations](docs/architecture.md#known-limitations).
Scanned PDFs need OCR upstream. Chunk assignment is lexical rather than embedding-based.
Cross-model verification degrades to a same-model check if only one API key is
configured. Two models with overlapping training data can still share a blind spot —
which is why `needs_human` exists.

## Documentation

| Doc | Contents |
| --- | --- |
| [architecture.md](docs/architecture.md) | Component map, audit sequence, verification design, limitations |
| [compliance-rules.md](docs/compliance-rules.md) | YAML rule format and how to author good synonyms |
| [setup-guide.md](docs/setup-guide.md) | Install, configure, run, troubleshoot |
| [build-plan.md](docs/build-plan.md) | Phase-by-phase build log and remaining work |


MIT — see [LICENSE](LICENSE).
