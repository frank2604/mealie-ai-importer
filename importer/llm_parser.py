"""Shared helpers for LLM-based recipe extraction.

Concrete client implementations live in ``llm_anthropic`` (Anthropic/Claude,
active) and the legacy ``llm_factory`` (OpenAI, no longer used). This module
only contains the shared data types and prompt-building utilities that both
clients depend on.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .models import Recipe
from .prompt_store import resolve_prompt
from .prompt_logging import log_prompt_messages, log_prompt_response  # noqa: F401 – re-exported for callers

logger = logging.getLogger(__name__)


class LlmParsingError(RuntimeError):
    """Raised when the LLM cannot produce a valid recipe."""


@dataclass
class LlmRequest:
    text: str
    source: Optional[Path]
    title_hint: Optional[str]
    servings_hint: Optional[str]
    locale: str = "de"


_DEFAULT_ANALYSIS_SYSTEM = "Du bist ein hilfreicher Assistent, der Rezepttexte in eine strukturierte JSON-Darstellung für die App Mealie überführt."

_DEFAULT_ANALYSIS_USER_TEMPLATE = (
    "Kontext:\n"
    "- Titel-Hinweis: {title_hint}\n"
    "- Dateiname: {filename}\n"
    "- Hinweis Portionen: {servings}\n\n"
    "Rezepttext:\n---\n{text}\n---"
)


def _build_analysis_user_prompt(user1: str, user2: str, request: LlmRequest) -> str:
    parts = [part.strip() for part in (user1, user2) if part and part.strip()]
    if parts:
        return "\n\n".join(parts).strip()

    locale = (request.locale or "de").lower()
    is_english = locale.startswith("en")
    unknown = "unknown" if is_english else "unbekannt"
    title_hint = request.title_hint or unknown
    servings_hint = request.servings_hint or unknown
    source_name = str(request.source) if request.source else unknown
    return _DEFAULT_ANALYSIS_USER_TEMPLATE.format(
        filename=source_name,
        servings=servings_hint,
        title_hint=title_hint,
        text=request.text,
    )


def parse_with_llm(
    text: str,
    *,
    llm_client: Any,
    source: Optional[Path] = None,
    servings_hint: Optional[str] = None,
    title_hint: Optional[str] = None,
    locale: str = "de",
    llm_config: Optional[Dict[str, Any]] = None,
) -> Recipe:
    """Parse *text* using the provided LLM client and return a Recipe."""
    cleaned_text = text.strip()
    if not cleaned_text:
        raise LlmParsingError("Leerer Rezepttext – prüfe die PDF-Extraktion")

    request = LlmRequest(
        text=cleaned_text,
        source=source,
        title_hint=None,
        servings_hint=None,
        locale=locale or "de",
    )

    logger.debug("Sende %s Zeichen an das LLM", len(cleaned_text))
    return llm_client.run(request, llm_config=llm_config)
