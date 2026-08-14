"""Single source of truth for models, credentials, and runtime limits.

No model name or numeric limit is hardcoded anywhere else in the codebase. If you
find yourself typing a model string into an agent module, it belongs here instead.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
RULES_DIR = Path(__file__).resolve().parent / "rules"


def load_prompt(name: str) -> str:
    """Load a system prompt by stem from `agent/prompts/`.

    Prompts live on disk rather than in string literals because they are the real
    logic of this system and deserve to show up in diffs.
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Providers -----------------------------------------------------------
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    # Workers and the planner reason with Claude.
    worker_model: str = "claude-sonnet-5"
    planner_model: str = "claude-sonnet-5"

    # The verifier deliberately runs on a *different* provider, so that a shared
    # hallucination has to survive two independently trained models.
    verifier_model: str = "gemini-2.5-pro"
    verifier_provider: str = Field(default="google", pattern="^(google|anthropic)$")

    # --- Runtime limits ------------------------------------------------------
    max_agent_turns: int = Field(default=25, ge=1)
    max_verification_strategies: int = Field(default=3, ge=1, le=5)
    max_output_tokens: int = Field(default=4096, ge=256)
    worker_concurrency: int = Field(default=4, ge=1)

    # Findings at or below this confidence get escalated even when PRESENT.
    verification_confidence_floor: float = Field(default=0.7, ge=0.0, le=1.0)

    # --- Chunking ------------------------------------------------------------
    chunk_target_chars: int = Field(default=6000, ge=500)
    chunk_overlap_blocks: int = Field(default=1, ge=0)

    # --- Paths ---------------------------------------------------------------
    report_dir: Path = REPO_ROOT / "reports"
    trace_dir: Path = REPO_ROOT / "runs"

    @property
    def has_verifier_credentials(self) -> bool:
        """Whether a genuine cross-model check is possible with current keys."""
        if self.verifier_provider == "google":
            return bool(self.google_api_key)
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor. Call `get_settings.cache_clear()` in tests."""
    return Settings()
