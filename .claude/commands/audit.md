---
description: Run an audit on a contract and summarize what the agents actually did
---

Run the pipeline and explain the result.

Contract: $ARGUMENTS (default: `agent/tests/fixtures/sample_nda.pdf`)

Steps:

1. Run `uv run ldd audit <contract> --markdown --verbose`.
2. Read the trace at `runs/<audit_id>/trace.jsonl`.
3. Summarize:
   - Confirmed gaps, with severity, and what each one exposes commercially.
   - **Every verifier overturn** — which worker claimed missing, which strategy
     located the clause, and what wording the worker missed. This is the part worth
     reporting; a run with zero overturns is worth flagging as suspicious.
   - Anything routed to `needs_human`, and why it was genuinely ambiguous.
   - Wall-clock time and worker concurrency from the trace.

If a worker errored, say so plainly rather than reporting a partial audit as complete.

Do not modify code unless I ask.
