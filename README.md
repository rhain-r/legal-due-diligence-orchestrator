## Legal Due Diligence Orchestrator
An Agentic AI system that operates as an autonomous legal due diligence orchestrator. Unlike linear automations, this multi-agent architecture utilizes an adversarial reasoning loop to audit complex contracts, make independent decisions about compliance risks, and use tools to securely parse documents, verify absence claims, and generate deterministic risk reports.

Instead of manually skimming hundreds of pages to prove what an agreement doesn't say, this system gives AI agents access to your legal documents and compliance rulebooks, allowing them to execute your firm's Standard Operating Procedures (SOPs) autonomously while actively preventing "lazy LLM" false negatives.

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

## Backend Demonstration

![Verification loop recovering eight clauses](assets/demo.svg)

## Try it out!

| [Live &rarr;](https://rhain-r.github.io/legal-due-diligence-orchestrator/) | A guided walkthrough |
| --- | ---|
---

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

---

## Challenges Solved

* **The "Lazy LLM" Problem:** A model skimming a 90-page MSA will often say "no clause found" just to save compute. 
  * *Solution:* **Adversarial Verification.** The verifier is forced to use a different retrieval strategy (synonym search + section scans) and a different model (Gemini vs. Claude), with the burden of proof inverted.
 <br></br>
* **Hallucinated Quotes:** LLMs notoriously invent text that sounds legally plausible.
  * *Solution:* **Citation Gates.** A custom `cite_source()` function verifies quotes against the anchored `(page, ¶, §)` source text before minting a Citation object.
<br></br>
* **Self-Contradictory JSON:** Agents often output a status of "MISSING" while providing a quote of the clause.
  * *Solution:* **Schema-Enforced Integrity.** Pydantic v2 with `extra="forbid"` throws a `ValidationError` if an agent submits logically impossible combinations.
<br></br>

---

## Evaluation

| Worker | | Precision | Recall | F1 | FP | FN |
| --- | --- | --- | --- | --- | --- | --- |
| Keyword-blind | workers only | 0.222 | 0.667 | 0.333 | 21 | 3 |
| Keyword-blind | **+ verification** | **0.462** | **0.667** | **0.546** | **7** | **3** |
| Synonym-aware | workers only | 0.417 | 0.556 | 0.477 | 7 | 4 |
| Synonym-aware | + verification | 0.417 | 0.556 | 0.477 | 7 | 4 |

---

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

## Documentation

| Doc | Contents |
| --- | --- |
| [architecture.md](docs/architecture.md) | Component map, audit sequence, verification design, limitations |
| [compliance-rules.md](docs/compliance-rules.md) | YAML rule format and how to author good synonyms |
| [setup-guide.md](docs/setup-guide.md) | Install, configure, run, troubleshoot |
| [build-plan.md](docs/build-plan.md) | Phase-by-phase build log and remaining work |


