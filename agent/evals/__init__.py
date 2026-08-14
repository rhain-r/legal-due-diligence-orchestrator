"""Evaluation harness.

Measures the *architecture*, not the models. The simulated agents in
`simulated.py` are deterministic stand-ins; what is being scored is whether the
retrieval ladder, citation gate, and schema enforcement recover from the kinds of
mistakes a shallow reviewer makes.

Answer keys are consulted only by the scorer. No agent ever sees them.
"""

from __future__ import annotations

from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent
GOLDEN_DIR = EVALS_DIR / "golden"
BUILD_DIR = GOLDEN_DIR / "build"
RESULTS_DIR = EVALS_DIR / "results"
