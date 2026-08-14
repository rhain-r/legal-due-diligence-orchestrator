"""Message contracts between agents.

In a multi-agent system the schema *is* the architecture: agents share messages,
not memory. Everything crossing an agent boundary is defined here and validated
on the way through. `extra="forbid"` means a model that invents a field gets a
validation error rather than a silently ignored hallucination.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base for every contract: unknown fields are an error, not a shrug."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --- Enumerations ------------------------------------------------------------


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


SEVERITY_WEIGHT: dict[Severity, float] = {
    Severity.CRITICAL: 10.0,
    Severity.HIGH: 6.0,
    Severity.MEDIUM: 3.0,
    Severity.LOW: 1.0,
}


class FindingStatus(str, Enum):
    PRESENT = "present"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    NON_COMPLIANT = "non_compliant"


class Verdict(str, Enum):
    CONFIRMED = "confirmed"
    OVERTURNED = "overturned"
    NEEDS_HUMAN = "needs_human"


class SearchStrategy(str, Enum):
    """How a piece of text was located.

    The verifier is required to use a strategy the worker did not. Re-reading the
    same way and getting the same answer is agreement, not verification.
    """

    SEMANTIC = "semantic"
    LEXICAL = "lexical"
    SYNONYM = "synonym"
    SECTION_SCAN = "section_scan"
    FULL_TEXT = "full_text"


# --- Document primitives -----------------------------------------------------


class TextBlock(StrictModel):
    """One paragraph, still carrying where it came from.

    The anchor survives parsing and chunking, which is the only reason
    `cite_source()` can return a location a lawyer can actually open.
    """

    block_id: str
    page: int = Field(ge=1)
    paragraph: int = Field(ge=0)
    text: str
    section_ref: str | None = None
    char_start: int = Field(default=0, ge=0)

    @property
    def locator(self) -> str:
        base = f"p.{self.page} ¶{self.paragraph}"
        return f"§{self.section_ref} ({base})" if self.section_ref else base


class Chunk(StrictModel):
    """The unit of delegation. A worker sees chunks, never the whole document."""

    chunk_id: str
    blocks: list[TextBlock] = Field(min_length=1)

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    @property
    def page_start(self) -> int:
        return min(b.page for b in self.blocks)

    @property
    def page_end(self) -> int:
        return max(b.page for b in self.blocks)

    @property
    def section_refs(self) -> list[str]:
        seen: dict[str, None] = {}
        for b in self.blocks:
            if b.section_ref:
                seen.setdefault(b.section_ref, None)
        return list(seen)

    def render(self) -> str:
        """Chunk text annotated with locators, as handed to a model."""
        return "\n\n".join(f"[{b.block_id} | {b.locator}]\n{b.text}" for b in self.blocks)


# --- Compliance rules --------------------------------------------------------


class ComplianceRule(StrictModel):
    """One line item in the firm's SOP."""

    rule_id: str
    clause_name: str
    domain: str
    description: str
    synonyms: list[str] = Field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    required: bool = True

    @property
    def search_terms(self) -> list[str]:
        terms = [self.clause_name, *self.synonyms]
        seen: dict[str, None] = {}
        for t in terms:
            seen.setdefault(t.lower().strip(), None)
        return [t for t in seen if t]


# --- Findings ----------------------------------------------------------------


class Citation(StrictModel):
    """A verbatim quote bound to its location. Produced only by `cite_source()`."""

    page: int = Field(ge=1)
    paragraph: int = Field(ge=0)
    section_ref: str | None = None
    quote: str = Field(min_length=1, max_length=500)
    block_id: str | None = None
    fuzzy_match: bool = False

    def __str__(self) -> str:
        loc = f"§{self.section_ref}, " if self.section_ref else ""
        return f"{loc}p.{self.page} ¶{self.paragraph}"


class SearchEvidence(StrictModel):
    """What an agent actually did before claiming something is absent.

    An absence claim without this is an opinion. With it, it is auditable.
    """

    strategy: SearchStrategy
    terms_searched: list[str] = Field(default_factory=list)
    sections_scanned: list[str] = Field(default_factory=list)
    blocks_examined: int = Field(default=0, ge=0)


class Finding(StrictModel):
    """A single compliance observation from one worker about one rule."""

    finding_id: str = Field(default_factory=lambda: f"fnd_{uuid4().hex[:10]}")
    contract_id: str
    rule_id: str
    clause_name: str
    agent_name: str
    status: FindingStatus
    severity: Severity = Severity.MEDIUM
    rationale: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    evidence: SearchEvidence | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _enforce_evidentiary_rules(self) -> Finding:
        """The core integrity rule of the system.

        A clause claimed present must point at text. A clause claimed absent
        cannot point at text, and must instead show the search that failed.
        """
        found = (FindingStatus.PRESENT, FindingStatus.NON_COMPLIANT)
        if self.status in found and not self.citations:
            raise ValueError(
                f"status={self.status.value} requires at least one citation; "
                "a clause cannot be reported as found without quoting it"
            )
        if self.status is FindingStatus.MISSING:
            if self.citations:
                raise ValueError(
                    "status=missing cannot carry citations; a quote from the document "
                    "contradicts the claim that the clause is absent"
                )
            if self.evidence is None:
                raise ValueError(
                    "status=missing requires SearchEvidence; an unsupported absence "
                    "claim is exactly the failure mode this system exists to prevent"
                )
        return self

    @property
    def needs_verification(self) -> bool:
        return self.status is FindingStatus.MISSING or self.confidence < 0.7


class VerificationResult(StrictModel):
    """The verifier's ruling on one finding."""

    finding_id: str
    verdict: Verdict
    strategies_used: list[SearchStrategy] = Field(default_factory=list)
    counter_citations: list[Citation] = Field(default_factory=list)
    reasoning: str
    verifier_model: str | None = None

    @model_validator(mode="after")
    def _overturn_needs_proof(self) -> VerificationResult:
        if self.verdict is Verdict.OVERTURNED and not self.counter_citations:
            raise ValueError(
                "verdict=overturned requires counter_citations; overturning a finding "
                "means the clause was located, so it must be quotable"
            )
        return self


# --- Report ------------------------------------------------------------------


class AuditReport(StrictModel):
    """The deliverable. Strict enough to hand to a downstream system."""

    audit_id: str = Field(default_factory=lambda: f"aud_{uuid4().hex[:10]}")
    contract_id: str
    source_file: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    rules_evaluated: int = Field(ge=0)
    findings: list[Finding] = Field(default_factory=list)
    verifications: list[VerificationResult] = Field(default_factory=list)
    overturned: list[Finding] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    page_count: int = Field(default=0, ge=0)

    @property
    def confirmed_gaps(self) -> list[Finding]:
        return [f for f in self.findings if f.status is FindingStatus.MISSING]

    @property
    def verifier_lift(self) -> int:
        """How many worker findings the verifier caught. Justifies the architecture."""
        return len(self.overturned)
