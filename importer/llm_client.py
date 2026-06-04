"""Minimal Protocol describing the LLM client interface.

All three concrete implementations (AnthropicClient, and the legacy
OpenAiClient) satisfy this protocol via structural subtyping (duck typing).
Use ``LLMClient`` for type hints instead of importing a concrete class —
that way the modules stay independent of whichever backend is active.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
from typing import Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from .llm_parser import LlmRequest
    from .models import Recipe


@runtime_checkable
class LLMClient(Protocol):
    """Structural protocol for LLM clients used throughout the pipeline."""

    def run(
        self,
        request: "LlmRequest",
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> "Recipe":
        """Parse a recipe from raw text and return a structured Recipe."""
        ...

    def run_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return a plain-text response for lightweight prompts."""
        ...

    def run_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a structured JSON response (forced tool-use / JSON mode)."""
        ...
