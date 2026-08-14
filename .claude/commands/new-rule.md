---
description: Add a compliance rule to an SOP, with synonyms that give the verifier a chance
---

Add a new compliance rule: $ARGUMENTS

Read `docs/compliance-rules.md` first, then:

1. Append the rule to the appropriate file in `agent/rules/` (default
   `nda_sop.yaml`). Follow the existing field order and `>-` block style.
2. Write `description` as an **obligation a lawyer could rule on**, not a topic.
   "Check the liability clause" is useless; "Liability must be limited by an
   aggregate cap, and consequential damages excluded" is a specification.
3. Populate `synonyms` with the words the clause **actually uses in practice**, not
   its formal name. A cap on damages rarely contains the phrase "cap on damages" —
   it says "in no event shall", "shall not exceed", "aggregate obligation". This
   field is what lets the verifier find a clause the worker missed; a thin synonym
   list is the most common cause of a false absence claim.
4. If the rule introduces a new `domain`, add matching entries to `LEGAL_EXPANSIONS`
   in `agent/tools/search.py`.
5. Add a test in `agent/tests/test_reporting.py` asserting the rule loads and its
   `search_terms` deduplicate correctly.
6. Run `uv run ldd rules` and `uv run pytest` and show me the output.

Then tell me which existing fixture contracts would now fail this rule, if any.
