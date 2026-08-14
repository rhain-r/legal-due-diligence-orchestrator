<h1 align="center">Legal Due Diligence Orchestrator</h1>

<p align="center">
  <strong>A multi-agent AI system that audits legal contracts against a firm's compliance SOP — then argues with itself to make sure it's right.</strong>
</p>

<p align="center">
  <img alt="Python 3.10–3.13" src="https://img.shields.io/badge/python-3.10--3.13-3776AB?logo=python&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/reasoning-Claude%20Sonnet-D97757">
  <img alt="Gemini" src="https://img.shields.io/badge/verification-Gemini-4285F4?logo=google&logoColor=white">
  <img alt="Pydantic v2" src="https://img.shields.io/badge/validation-Pydantic%20v2-E92063">
  <img alt="Tests" src="https://img.shields.io/badge/tests-65%20passing-2ea043">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-blue">
</p>

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

## What makes it more than a RAG wrapper

| Capability | Why it matters |
| --- | --- |
| **Adversarial verification** | The verifier must use a strategy the worker didn't, and is prompted to *find* the clause rather than confirm its absence. Re-asking the same way is agreement, not verification. |
| **Cross-model second opinion** | Workers reason on Claude; the verifier runs on Gemini. Two independently trained models converging on "absent" is real evidence. One model agreeing with itself is not. |
| **Citation gate** | `cite_source()` verifies a quote appears in the source before minting a `Citation`. An agent can hallucinate a quote; it cannot hallucinate a citation. |
| **Schema-enforced integrity** | A `MISSING` finding carrying a document quote raises a `ValidationError` — the claim is self-contradictory. `extra="forbid"` turns invented fields into errors. |
| **Anchored parsing** | `(page, ¶, §)` survives parsing and chunking, so citations point at somewhere a lawyer can actually open. |
| **Three verdicts, not two** | `needs_human` is a first-class outcome. A flagged ambiguity costs a five-minute review; a wrong "confirmed" costs a missed liability. |
| **Deterministic scoring** | Risk score is a Python function of severity and status — auditable, explainable, unit-tested. Not a number an LLM felt like emitting. |

## Quick start

```bash
git clone https://github.com/rhain-r/legal-due-diligence-orchestrator.git
```

```bash
cd legal-due-diligence-orchestrator && uv sync --extra dev
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
└── tests/             65 tests, all against stubbed clients
assets/                architecture diagram
docs/                  architecture · compliance-rules · setup-guide · build-plan
```

Roughly two-thirds of the system is deterministic Python. Everything that *can* be a
tested function instead of a prompt, is one — which is why the whole suite runs in
under a second with no API key and no cost.

## Testing

```bash
uv run pytest
```

```
65 passed in 0.91s
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
CLI. 65 tests passing, `ruff` clean.

**Not yet built:** the eval harness ([build plan](docs/build-plan.md) Phase 9). Until
it exists, the accuracy argument in this README is *architectural*, not measured —
there are no benchmark numbers here and I'm not going to imply otherwise.

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

## License

MIT — see [LICENSE](LICENSE).
