"""Loading compliance SOPs from YAML.

Rules are data, not code. A firm should be able to add a review item by editing
YAML, without touching a Python file or redeploying anything.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from agent.config import RULES_DIR
from agent.schemas import ComplianceRule


class SOP(BaseModel):
    """A named, versioned set of compliance rules."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str = "1.0"
    description: str = ""
    rules: list[ComplianceRule] = Field(min_length=1)

    @property
    def domains(self) -> list[str]:
        seen: dict[str, None] = {}
        for rule in self.rules:
            seen.setdefault(rule.domain, None)
        return list(seen)


def load_sop(path: str | Path) -> SOP:
    """Load and validate an SOP file.

    A bare filename resolves against `agent/rules/`, so `--rules nda_sop.yaml`
    works from anywhere.
    """
    candidate = Path(path)
    if not candidate.exists() and not candidate.is_absolute():
        candidate = RULES_DIR / candidate.name
    if not candidate.exists():
        available = ", ".join(p.name for p in sorted(RULES_DIR.glob("*.yaml"))) or "(none)"
        raise FileNotFoundError(f"SOP not found: {path}. Available in agent/rules/: {available}")

    data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{candidate.name} must be a YAML mapping with a 'rules' list.")
    return SOP.model_validate(data)


def load_rules(path: str | Path) -> list[ComplianceRule]:
    """Just the rules, for callers that do not need SOP metadata."""
    return load_sop(path).rules
