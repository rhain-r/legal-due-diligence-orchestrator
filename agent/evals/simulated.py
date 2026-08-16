"""Deterministic stand-ins for the worker and verifier models.

**Read this before trusting any number the harness prints.**

These are not language models and they do not reason. They are lexical
heuristics that occupy the same position in the pipeline a model would, so the
harness can exercise the parts of the system that *are* real: chunk assignment,
the retrieval ladder, the citation gate, schema enforcement, verdict routing,
and report assembly.

What that means for interpreting results:

- The scores characterise **pipeline recovery behaviour**, not model accuracy.
  Swapping in `AnthropicClient` and `GeminiClient` would produce entirely
  different numbers, and those would be the ones worth quoting about models.
- The asymmetry between the two stand-ins mirrors the asymmetry the architecture
  is built on. The worker reads for the clause it was told to find. The verifier
  searches the whole document for *operative language* — a modal obligation
  attached to the topic, with negations and non-committal recitals rejected.
- Neither stand-in ever reads a golden answer key. Ground truth is used only by
  the scorer.

`WorkerStrength` exists so results are not cherry-picked. `NAIVE` matches on the
clause name alone; `SYNONYM` also matches the SOP's synonym list. Reporting both
shows how much of the verifier's measured lift is an artifact of a weak worker
rather than a property of the architecture.
"""

from __future__ import annotations

import json
import re
from enum import Enum

from agent.schemas import ComplianceRule

# Blocks arrive rendered as "[block_id | locator]\ntext".
_BLOCK_RE = re.compile(r"^\[(?P<id>\S+) \| (?P<loc>[^\]]+)\]\n(?P<text>.*)$", re.M)
_CLAUSE_RE = re.compile(r"\*\*Clause:\*\*\s*(?P<clause>.+?)\s*$", re.M)

_STOPWORDS = {"of", "the", "and", "or", "on", "in", "to", "a", "for", "no", "by"}

#: A duty is created by a modal verb, not by a topic being mentioned.
_MODALS = (
    "shall",
    "must",
    "undertakes",
    "agrees to",
    "is entitled",
    "may seek",
    "may apply",
    "may retain",
    "will not",
)

#: Definitional rules are satisfied by a defining verb rather than a duty.
#: "'Protected Material' comprises..." creates the defined term the SOP requires.
_DEFINITIONAL = ("means", "comprises", "refers to", "is defined as")

#: Provisions that state a legal effect without commanding anyone: a term that
#: "remains in force", rights a party "retains", a carve-out that "does not
#: apply". Omitting these was a defect in this stand-in, not a finding about the
#: architecture.
#:
#: This list was expanded exactly once, on principle, after inspecting which
#: constructions were being missed — and then frozen. It is deliberately not
#: tuned further against the golden set, because a heuristic iterated until the
#: scores look good measures nothing except the iteration.
_EFFECTIVE = (
    "remains in force",
    "remain in force",
    "remains in effect",
    "retains all",
    "retain all",
    "does not include",
    "shall not include",
    "do not apply",
    "does not apply",
    "do not bite",
    "survive",
    "continues for",
    "continue to bind",
    "is governed",
    "are governed",
    "governed by",
    "are determined in accordance",
    "takes effect",
    "transfers or licenses",
)

_OPERATIVE = _MODALS + _DEFINITIONAL + _EFFECTIVE

#: Language that discusses an obligation without creating one.
_VACUOUS = (
    "acknowledge the importance",
    "were considered",
    "have discussed",
    "recognise the sensitivity",
    "recognize the sensitivity",
    "wish to explore",
    "intend that this agreement record",
)

#: Language that cancels the obligation it appears to create.
_NEGATORS = (
    "no obligation to",
    "have no obligation",
    "shall have no obligation",
    "operate to limit",
    "remain fully liable",
    "nothing in this agreement shall operate",
)


class WorkerStrength(str, Enum):
    NAIVE = "naive"
    SYNONYM = "synonym"


# --- Prompt parsing ----------------------------------------------------------


def parse_blocks(prompt: str) -> list[tuple[str, str]]:
    """Recover (block_id, text) pairs from a rendered excerpt."""
    return [(m.group("id"), m.group("text")) for m in _BLOCK_RE.finditer(prompt)]


class PromptFormatError(RuntimeError):
    """The prompt no longer carries the field the stand-in reads."""


def parse_clause_name(system: str) -> str:
    """Extract the clause under review from a system prompt.

    Raises rather than returning "" on a miss. A silent empty string would make
    every stand-in return a fixed answer — all `missing` from the worker, never
    overturned by the verifier — and the harness would print a full set of
    plausible, entirely different numbers with a zero exit code. Published eval
    figures are worth an exception here.
    """
    match = _CLAUSE_RE.search(system)
    if not match or not match.group("clause").strip():
        raise PromptFormatError(
            "Could not find '**Clause:** <name>' in the system prompt. The simulated "
            "agents parse the same prompt a model reads, so a change to "
            "agent/prompts/*.md must be mirrored in agent/evals/simulated.py."
        )
    return match.group("clause").strip()


def _tokens(phrase: str) -> list[str]:
    words = re.findall(r"[a-z]+", phrase.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def _best_sentence(text: str, needles: list[str]) -> str:
    """Exact substring of `text` most dense in `needles`, for a verbatim quote."""
    best, best_score = text[:300], -1
    for match in re.finditer(r"[^.;]+[.;]?", text):
        sentence = match.group(0).strip()
        if len(sentence) < 20:
            continue
        lowered = sentence.lower()
        score = sum(1 for n in needles if n in lowered)
        if score > best_score:
            best, best_score = sentence[:300], score
    return best


# --- Worker ------------------------------------------------------------------


class SimulatedWorkerClient:
    """Stands in for a clause worker that reads for the clause it was assigned.

    Models the failure the verifier exists to catch: a reviewer who recognises a
    clause by its name and misses one that does the same legal work under
    different words.
    """

    def __init__(
        self,
        rules: list[ComplianceRule],
        strength: WorkerStrength = WorkerStrength.NAIVE,
    ) -> None:
        self._by_clause = {r.clause_name.lower(): r for r in rules}
        self.strength = strength
        self.name = f"simulated-worker[{strength.value}]"
        self.calls = 0

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        self.calls += 1
        clause = parse_clause_name(system)
        rule = self._by_clause.get(clause.lower())
        blocks = parse_blocks(prompt)

        needles = _tokens(clause)
        phrases: list[str] = []
        if rule and self.strength is WorkerStrength.SYNONYM:
            phrases = [s.lower() for s in rule.synonyms]

        best_block, best_score = None, 0.0
        for _, text in blocks:
            lowered = text.lower()
            token_hits = sum(1 for t in needles if t in lowered)
            score = token_hits / len(needles) if needles else 0.0
            if phrases and any(p in lowered for p in phrases):
                score = max(score, 1.0)
            if score > best_score:
                best_block, best_score = text, score

        if best_block is not None and best_score >= 0.6:
            return json.dumps(
                {
                    "status": "present",
                    "rationale": (
                        f"Language matching '{clause}' appears in the assigned excerpts."
                    ),
                    "quotes": [_best_sentence(best_block, needles)],
                    "confidence": 0.9 if best_score >= 0.99 else 0.62,
                }
            )

        return json.dumps(
            {
                "status": "missing",
                "rationale": (
                    f"No language matching '{clause}' was found in the assigned excerpts."
                ),
                "quotes": [],
                "terms_searched": [clause, *phrases],
                "sections_scanned": [],
                "confidence": 0.8,
            }
        )


# --- Verifier ----------------------------------------------------------------


class SimulatedVerifierClient:
    """Stands in for the adversarial verifier.

    Judges *operative effect* rather than topic: a block counts only if it pairs
    a modal obligation with the clause's subject matter, and is neither a
    non-committal recital nor an obligation cancelled by its own wording.

    The blocks it sees were retrieved by the real ladder in `verifier.py`, so
    what is being measured here is genuinely whether synonym expansion and
    section scanning surface the right text.
    """

    def __init__(self, rules: list[ComplianceRule]) -> None:
        self._by_clause = {r.clause_name.lower(): r for r in rules}
        self.name = "simulated-verifier"
        self.calls = 0

    @staticmethod
    def _on_topic(text: str, clause_tokens: list[str], synonyms: list[str]) -> bool:
        """Clause-specific topic test.

        Deliberately does NOT use `LEGAL_EXPANSIONS`. Domain expansion belongs to
        retrieval, where casting a wide net is cheap and a miss is expensive.
        Judging has to be clause-specific: "return of materials" and "definition
        of confidential information" share a domain, so a domain-level match
        would let any confidentiality paragraph satisfy either rule.
        """
        lowered = text.lower()
        if any(s in lowered for s in synonyms):
            return True
        if not clause_tokens:
            return False
        hits = sum(1 for t in clause_tokens if t in lowered)
        return hits / len(clause_tokens) >= 0.6

    def _is_operative(self, text: str, clause_tokens: list[str], synonyms: list[str]) -> bool:
        lowered = text.lower()
        if any(v in lowered for v in _VACUOUS):
            return False
        if any(n in lowered for n in _NEGATORS):
            return False
        if not any(m in lowered for m in _OPERATIVE):
            return False
        return self._on_topic(text, clause_tokens, synonyms)

    async def complete(self, system: str, prompt: str, *, max_tokens: int) -> str:
        self.calls += 1
        clause = parse_clause_name(system)
        rule = self._by_clause.get(clause.lower())
        clause_tokens = _tokens(clause)
        synonyms = [s.lower() for s in rule.synonyms] if rule else []

        for _, text in parse_blocks(prompt):
            if self._is_operative(text, clause_tokens, synonyms):
                return json.dumps(
                    {
                        "verdict": "overturned",
                        "reasoning": (
                            f"Operative language creating the '{clause}' obligation was "
                            "located by whole-document retrieval."
                        ),
                        "quotes": [_best_sentence(text, [*clause_tokens, *synonyms])],
                    }
                )

        return json.dumps(
            {
                "verdict": "confirmed",
                "reasoning": (
                    f"No operative language creating the '{clause}' obligation was found. "
                    "Topic references without a modal duty were rejected."
                ),
                "quotes": [],
            }
        )
