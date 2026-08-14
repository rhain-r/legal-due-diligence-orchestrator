# Architecture

![Agent architecture](../assets/architecture.svg)

## The problem being solved

Contract review tools are good at reporting what a document says. The expensive
paralegal work is proving what a document **doesn't** say — that there's no cap on
damages, no governing-law clause, no return-of-materials obligation.

That is also where language models fail hardest, and fail *quietly*. A model that
skims a 90-page agreement and reports "no limitation of liability found" produces
output identical to a model that looked carefully and found nothing. There is no
signal in the response that distinguishes diligence from laziness.

So the system is built on one premise: **an absence claim is untrusted until an
adversary fails to overturn it.**

## Component map

| Layer | Module | LLM? | Responsibility |
| --- | --- | --- | --- |
| Contracts | `agent/schemas.py` | no | Every message crossing an agent boundary |
| Ingestion | `agent/ingestion/` | no | PDF → blocks anchored to (page, ¶, §) → chunks |
| Tools | `agent/tools/` | no | `cite_source()`, lexical / synonym / section retrieval |
| Config | `agent/config.py` | no | Models, keys, limits. Nothing hardcoded elsewhere |
| Model access | `agent/llm.py` | — | Provider adapters + structured output with retry |
| Workers | `agent/workers.py` | yes | One clause domain each |
| Verifier | `agent/verifier.py` | yes | Adversarial challenge |
| Lead | `agent/orchestrator.py` | yes | Plan, dispatch, route, trace |
| Output | `agent/reporter.py` | no | Scoring, JSON, terminal, markdown |

Roughly two-thirds of the system is deterministic Python. That ratio is deliberate.
Everything that *can* be a tested function instead of a prompt, is one.

## Sequence of one audit

1. **Ingest.** `parse_pdf` yields `TextBlock`s carrying page, paragraph, and section.
   Normalization removes running headers, page-number lines, and hyphenated line
   wraps. `chunk_blocks` groups them without ever splitting a paragraph.
2. **Plan.** The orchestrator scopes each rule to chunks matching its search terms,
   falling back to the whole document on a miss.
3. **Dispatch.** Workers run concurrently under a semaphore. Each sees only its
   assigned chunks.
4. **Parse.** Output goes through `complete_structured`, which validates against the
   Pydantic model and, on failure, feeds the *validation error itself* back to the
   model as a correction signal. Output is never coerced.
5. **Gate citations.** Every quote is checked against the source by `cite_source()`.
   A worker claiming `present` with an unverifiable quote is downgraded to `missing`,
   not trusted.
6. **Verify.** Every `MISSING` finding, and everything below the confidence floor,
   goes to the verifier.
7. **Report.** Surviving findings are scored and serialized.

Every step appends to `runs/<audit_id>/trace.jsonl`.

## Why the verification loop is structured this way

A verifier that re-reads the document the same way, with the same model, and asks
the same question will produce the same answer with the same confidence. That is
agreement, not verification. Three properties break the correlation:

**1. Different retrieval strategy.** Workers read semantically over assigned chunks.
The verifier runs an escalating ladder over the *entire* document:

| Step | Strategy | Rationale |
| --- | --- | --- |
| 1 | Synonym expansion | The clause is usually present under different words |
| 2 | Catch-all section scan | Standard protections get buried in "General Provisions" |
| 3 | Full-text pass, one narrow question | Expensive, so it runs last |

**2. Different model.** Workers run on Claude; the verifier runs on Gemini. Two
independently trained models converging on "absent" is meaningfully stronger
evidence than one model agreeing with itself.

**3. Inverted burden of proof.** The verifier is prompted to *find* the clause, not
to confirm its absence. One verifiable hit overturns the finding. The verifier is
held to the same evidentiary standard as the worker: an overturn it cannot quote is
rejected and the ladder continues.

### Three outcomes, not two

- `overturned` — clause located. The finding is rewritten as `present`; the original
  is retained in the report's audit trail rather than deleted.
- `confirmed` — genuinely absent, with the full search record attached.
- `needs_human` — something arguably on point. A flagged ambiguity costs a five-minute
  review; a wrong `confirmed` costs a missed liability. The asymmetry is the whole
  reason this outcome exists.

A verifier failure (API error, exhausted retries) returns `needs_human`. It must
never read as agreement.

## Schema-enforced integrity

Two validators in `agent/schemas.py` carry most of the system's guarantees:

```python
# Finding
status in (PRESENT, NON_COMPLIANT) and not citations  -> ValueError
status is MISSING and citations                       -> ValueError
status is MISSING and evidence is None                -> ValueError

# VerificationResult
verdict is OVERTURNED and not counter_citations       -> ValueError
```

These are not stylistic. A `MISSING` finding that carries a quote from the document
is self-contradictory, and `extra="forbid"` means a model inventing a field gets an
error rather than a silently ignored hallucination.

## Framework independence

The orchestration is purpose-built rather than delegated to an agent framework.
`agent/llm.py` defines a `ModelClient` protocol with a single `complete()` method;
`AnthropicClient`, `GeminiClient`, and `StubClient` implement it.

The practical consequences:

- The entire test suite runs against `StubClient` — no keys, no network, no cost.
- Adding a provider means one class, not a migration.
- An AutoGen or LangGraph adapter is a `ModelClient` implementation plus a change to
  `_dispatch_workers`. Nothing in schemas, ingestion, tools, or reporting moves.

The delegation logic here is ~40 lines of `asyncio.gather` under a semaphore. A
framework would not have made that shorter, and would have made the verification
ladder harder to express.

## Known limitations

Stated plainly, because a portfolio repo that claims no weaknesses is not credible.

- **Scanned PDFs are unsupported.** `parse_pdf` raises rather than auditing an empty
  string, which would report every clause as missing. OCR must happen upstream.
- **Chunk assignment is lexical.** The planner scopes rules to chunks by term match,
  with a whole-document fallback. An embedding-based planner would scope tighter.
- **Paragraph granularity depends on the PDF.** Documents without blank-line
  separation degrade to line-level blocks. Citations stay correct but get finer.
- **The verifier only challenges absence claims.** This is the largest gap, and the
  eval quantifies it: every false negative in the golden set is a false-*presence*
  claim that was never challenged. A worker that confidently matches a reassuring
  heading — over a clause negating itself in its own body — is never contradicted.
  Symmetric verification of presence claims is the highest-value next change.
- **Never run against real models.** The system is wired for Claude and Gemini and
  will run against them, but every published number comes from the deterministic
  stand-ins in `agent/evals/simulated.py`. Those measure pipeline recovery, not model
  accuracy, and the repo makes no claim about the latter.
- **Verifier lift depends on SOP quality, not just architecture.** Against a
  synonym-aware worker the verifier eliminated zero false absence claims on the
  golden set, because good synonym lists had already caught them. The loop is a
  safety net for what the SOP misses, not a substitute for authoring it well.
- **Cross-model verification requires two API keys.** With only one provider
  configured the system still runs, but property 2 above degrades to a same-model
  check.
- **Correlated failure is not eliminated, only reduced.** Two models trained on
  overlapping corpora can share a blind spot. `needs_human` exists because of this.
