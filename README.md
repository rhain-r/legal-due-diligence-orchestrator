# Legal Due Diligence Orchestrator

**A multi-agent AI system that audits legal contracts against a firm's compliance SOP — and then argues with itself to make sure it's right.**

> **Status:** Architecture and build plan complete. Implementation in progress — see [docs/build-plan.md](docs/build-plan.md) for the phase-by-phase roadmap and current position.

---

## The problem this solves

Contract review tools are good at telling you what a document *says*. The expensive
paralegal work is proving what a document **doesn't** say — that the cap on damages
is missing, that there's no governing-law clause, that indemnification runs one way.

That's also exactly where LLMs fail hardest. A model that skims a 90-page master
services agreement and reports "no limitation of liability found" is indistinguishable
from a model that simply didn't look carefully. In legal work, that false negative is
the difference between a clean deal and an uncapped exposure.

This system treats **absence claims as untrusted by default**. Any agent that reports
a missing clause triggers a Verifier Agent that re-reads the document using a
deliberately *different* retrieval strategy before the finding is allowed into the report.

## Architecture

```
[ Document Ingestion ]
   PDF -> text blocks anchored to (page, paragraph)
       │
       ▼
[ Lead Agent: Plan Strategy ]
   Loads compliance SOP, assigns clause domains to workers
       │
       ├──► [ Worker: Liability ]     ──► "Uncapped risk, §7.1"
       ├──► [ Worker: Termination ]   ──► "Clause missing"
       ├──► [ Worker: Jurisdiction ]  ──► "Found, §4.2"
       │
       ▼
[ Verifier Agent: Challenge Findings ]
   Re-scans with synonym expansion + cross-model second opinion.
   Every MISSING claim must survive this to be reported.
       │
       ▼
[ Output Agent: Strict JSON Risk Report ]
   Pydantic-validated. Every finding carries a page/paragraph citation.
```

## What makes it more than a RAG wrapper

| Capability | Why it matters |
| --- | --- |
| **Hierarchical delegation** | Lead agent scopes each worker to its own clause domain and only its assigned chunks — bounded context, bounded cost. |
| **Adversarial verification loop** | The verifier is required to use a *different* search strategy than the worker it's checking. Re-asking the same way is not verification. |
| **Cross-model second opinion** | Claude reasons; Gemini independently checks absence claims. Two models sharing a hallucination is far less likely than one. |
| **Citation-anchored parsing** | Text blocks keep `(page, paragraph)` anchors through chunking, so `cite_source()` returns a real location a lawyer can open. |
| **Strict structured output** | Pydantic v2 with `extra="forbid"`. Invalid agent output is retried, never coerced. |
| **Measured, not asserted** | An eval harness scores precision/recall against golden contracts with known planted omissions. The accuracy claim is a number, not a paragraph. |

## Example report output

*Illustrative — shape of the emitted JSON, not benchmark results.*

| Contract ID | Agent | Clause Checked | Finding | Verification |
| --- | --- | --- | --- | --- |
| NDA-8812 | `liability_worker` | Cap on Damages | `MISSING` | Confirmed by Verifier (3 strategies, 0 hits) |
| LSE-1049 | `jurisdiction_worker` | Governing Law | `PRESENT` — §4.2 | Auto-approved (citation verified) |

## Tech stack

| Component | Technology |
| --- | --- |
| Agent framework | Microsoft AutoGen |
| Reasoning engine | Anthropic Claude Sonnet 5 |
| Verification model | Google Gemini |
| Document parsing | `pypdf` |
| Validation | Pydantic v2 |
| Tooling | `uv`, `pytest`, `ruff` |
| Built with | Claude Code |

## Getting started

```bash
git clone https://github.com/rhain-r/legal-due-diligence-orchestrator.git
cd legal-due-diligence-orchestrator
uv sync
cp .env.example .env    # add your API keys
uv run pytest -q
```

Run an audit against a sample contract:

```bash
uv run python -m agents.orchestrator --file tests/fixtures/nda_sample.pdf --rules rules/nda_sop.yaml
```

## Documentation

- [docs/build-plan.md](docs/build-plan.md) — phase-by-phase build tutorial
- [docs/architecture.md](docs/architecture.md) — agent topology and message contracts
- [docs/compliance-rules.md](docs/compliance-rules.md) — SOP rule format

## License

MIT
