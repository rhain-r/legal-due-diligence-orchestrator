# Authoring compliance rules

Rules are data, not code. A firm adds a review item by editing YAML — no Python
change, no redeploy.

Rule files live in `agent/rules/`. The bundled example is `nda_sop.yaml`.

## File format

```yaml
name: Mutual NDA Compliance SOP
version: "1.0"
description: Baseline review checklist for inbound mutual NDAs.

rules:
  - rule_id: NDA-006
    clause_name: Cap on Damages
    domain: liability
    description: >-
      Liability must be limited by an aggregate cap, and consequential and
      indirect damages must be excluded.
    synonyms:
      - limitation of liability
      - aggregate liability
      - shall not exceed
      - in no event
    severity: critical
    required: true
```

## Fields

| Field | Required | Purpose |
| --- | --- | --- |
| `rule_id` | yes | Stable identifier. Appears in every finding and report. |
| `clause_name` | yes | Human label. Shown in reports. |
| `domain` | yes | Groups rules and selects the verifier's expansion set. |
| `description` | yes | The actual requirement, in prose. Goes into the prompt. |
| `synonyms` | no, but see below | Alternative phrasings for the verifier. |
| `severity` | no | `critical` \| `high` \| `medium` \| `low`. Default `medium`. |
| `required` | no | Default `true`. |

## Writing a good `description`

This string goes verbatim into the worker and verifier prompts. It is the
specification the model is auditing against, so write it as an obligation, not a
topic.

| | |
| --- | --- |
| ❌ | `Liability stuff` |
| ❌ | `Check the liability clause` |
| ✅ | `Liability must be limited by an aggregate cap, and consequential and indirect damages must be excluded.` |

State the requirement so that a lawyer reading only that sentence could rule on it.

## Writing good `synonyms` — the part that matters

Synonyms are what let the verifier find a clause the worker missed. This is the
single highest-leverage field in the file.

**List the words the clause actually uses, not its formal name.** A cap on damages
almost never contains the phrase "cap on damages". It says:

> In no event shall either Party's aggregate obligation arising hereunder exceed
> the fees paid in the preceding twelve (12) months.

Shares zero keywords with "Cap on Damages". A worker searching the clause name finds
nothing and reports it missing. The verifier finds it via `in no event`.

Practical guidance:

- Include **operative sentence fragments**: `shall not exceed`, `in no event`,
  `hold harmless`, `governed by the laws of`.
- Include **common heading variants**: `Limitation of Liability`, `Liability Cap`.
- Include **British and American spellings** where they differ (`licence`/`license`).
- Don't include the clause name itself — it's added automatically.

Domain-level expansions in `agent/tools/search.py` (`LEGAL_EXPANSIONS`) are applied
on top of your synonyms for the domains `liability`, `termination`, `jurisdiction`,
`confidentiality`, and `indemnity`. Adding a new domain there benefits every rule
that uses it.

## Choosing `severity`

Severity drives the risk score via `SEVERITY_WEIGHT` in `agent/schemas.py`
(critical 10, high 6, medium 3, low 1). Scores are normalized against the maximum
possible for the rule set, so an 8-rule SOP and a 40-rule SOP produce comparable
numbers.

Reserve `critical` for clauses whose absence changes whether you'd sign.

## Adding a new SOP

1. Create `agent/rules/<name>.yaml` following the format above.
2. Validate it loads:

   ```bash
   uv run ldd rules --sop <name>.yaml
   ```

3. Run an audit against it:

   ```bash
   uv run ldd audit contract.pdf --rules <name>.yaml
   ```

`load_sop()` validates against the `SOP` Pydantic model, so a malformed file fails
immediately with a field-level error rather than midway through an audit.

## A note on scope

These rules encode a *checklist*, which is the right shape for structural review:
is the clause there, and does it do what it must? They do not encode negotiating
positions, market-standard thresholds, or client-specific risk appetite. Those are
judgement calls, and the system routes them to `needs_human` rather than pretending
to resolve them.
