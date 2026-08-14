# Setup guide

## Requirements

- **Python 3.10–3.13.** Not 3.14 — several dependencies don't support it yet.
  `uv` handles this for you; you do not need to change your system Python.
- **[uv](https://docs.astral.sh/uv/)** for dependency management.
- An **Anthropic API key**. A **Google API key** is optional but strongly
  recommended — cross-model verification is the point of the system.

## Install

```bash
git clone https://github.com/rhain-r/legal-due-diligence-orchestrator.git
```

```bash
cd legal-due-diligence-orchestrator
```

```bash
uv sync --extra dev
```

`uv` reads `.python-version`, fetches CPython 3.12 if it isn't present, and creates
`.venv/`. Your system Python is untouched.

Verify:

```bash
uv run pytest
```

65 tests should pass. They run entirely against stubbed model clients — no API key,
no network, no cost.

## Configure

Create a `.env` file in the repository root:

```bash
# Required — workers and planner
ANTHROPIC_API_KEY=sk-ant-...

# Recommended — the verifier runs on a different provider on purpose
GOOGLE_API_KEY=...

# Optional overrides (defaults shown)
WORKER_MODEL=claude-sonnet-5
PLANNER_MODEL=claude-sonnet-5
VERIFIER_MODEL=gemini-2.5-pro
VERIFIER_PROVIDER=google
MAX_AGENT_TURNS=25
MAX_VERIFICATION_STRATEGIES=3
WORKER_CONCURRENCY=4
VERIFICATION_CONFIDENCE_FLOOR=0.7
CHUNK_TARGET_CHARS=6000
```

`.env` is git-ignored. Never commit real keys.

If you only have an Anthropic key, set `VERIFIER_PROVIDER=anthropic`. The system
runs, but the verifier and the workers then share a model — a real weakening of the
guarantee, and the CLI warns you about it.

## Try it without spending anything

`inspect` parses a contract and shows its structure. No model calls, no key needed.
Run it against the bundled synthetic NDA:

```bash
uv run ldd inspect agent/tests/fixtures/sample_nda.pdf
```

```
sample_nda.pdf — 3 pages, 63 blocks, 9 sections, 1 chunks
```

Use this to confirm citations will anchor correctly before spending tokens. If the
section count looks wrong, the audit will inherit that error.

List the rules in an SOP, also free:

```bash
uv run ldd rules
```

## Run an audit

```bash
uv run ldd audit agent/tests/fixtures/sample_nda.pdf --markdown --verbose
```

Flags:

| Flag | Effect |
| --- | --- |
| `--rules`, `-r` | SOP file in `agent/rules/`. Default `nda_sop.yaml`. |
| `--out`, `-o` | Output directory. Default `reports/`. |
| `--markdown`, `-m` | Also write a memo-style summary. |
| `--verbose`, `-v` | Log agent activity, including verifier overturns. |

Outputs:

- `reports/<audit_id>.json` — strict-schema report
- `reports/<audit_id>.md` — memo, with `--markdown`
- `runs/<audit_id>/trace.jsonl` — every dispatch, finding, and verdict

Both `reports/` and `runs/` are git-ignored.

### What the sample contract is designed to show

The bundled NDA has planted characteristics:

- The **cap on damages is present** but buried in "General Provisions" and worded
  without the words "cap", "damages", or "limitation of liability". Expect at least
  one worker to report it missing and the verifier to overturn that.
- **Return/destruction of materials** and **injunctive relief** are genuinely absent.
  Those should survive verification as confirmed gaps.

Run with `--verbose` to watch the overturn happen. That moment is the system.

## Development

```bash
uv run pytest --cov=agent
```

```bash
uv run ruff check . --fix
```

Adding a dependency:

```bash
uv add <package>
```

## Troubleshooting

**`error: The Python request from .python-version resolved to Python 3.14.x`**
Your `.python-version` has a BOM or an unsupported version. Fix with
`uv python pin 3.12`.

**`Missing expected target directory for Python minor version link`**
A uv symlink issue on Windows. The interpreter still downloads correctly; pass it
explicitly:

```bash
uv sync --extra dev --python "$env:APPDATA\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe"
```

**`No extractable text in <file>.pdf`**
A scanned document. Run OCR before auditing — the system refuses rather than
reporting every clause as missing from an empty parse.

**`ANTHROPIC_API_KEY is not set`**
No `.env` file, or it's not in the directory you're running from.

**Verifier warning about credentials**
No `GOOGLE_API_KEY`. Either add one or set `VERIFIER_PROVIDER=anthropic`,
understanding the tradeoff.
