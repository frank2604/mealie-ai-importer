"""Anthropic (Claude) integration.

Drop-in replacement for :class:`importer.llm_parser.OpenAiClient`: it exposes the
exact same three methods (``run`` / ``run_text`` / ``run_json``) with identical
signatures, so every existing call site keeps working unchanged. Structured JSON
is obtained via Anthropic *forced tool use* (``tool_choice``), which is far more
reliable than parsing free text and replaces the old brittle ``json.loads``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import anthropic

from .models import Recipe
from .prompt_store import resolve_prompt
from .prompt_logging import log_prompt_messages, log_prompt_response
from .llm_parser import (
    LlmParsingError,
    LlmRequest,
    _build_analysis_user_prompt,
    _DEFAULT_ANALYSIS_SYSTEM,
)

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TOKENS = 4096

# Schema-agnostic emit tool: ``additionalProperties: true`` with no required keys
# lets every existing payload shape pass through ({"links": [...]},
# {"match": ...}, {"ingredients": [...]}, {"units": [...]}, the full recipe).
_EMIT_TOOL = {
    "name": "emit",
    "description": "Gib das strukturierte Ergebnis als JSON-Objekt zurück.",
    "input_schema": {"type": "object", "additionalProperties": True},
}
_FORCE_EMIT = {"type": "tool", "name": "emit"}


class AnthropicClient:
    """Minimal Claude client mirroring the OpenAiClient surface."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
        model_capabilities: Optional[Dict[str, bool]] = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._model_capabilities = {k.lower(): v for k, v in (model_capabilities or {}).items()}

        client_kwargs: Dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        # Only honour a custom base_url if it actually points at an Anthropic
        # host; the OpenAI default (api.openai.com) must never leak through.
        if base_url and "anthropic" in base_url:
            client_kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**client_kwargs)

    # ------------------------------------------------------------------
    # Capability shim (kept for format_llm_log / services.ingredients)
    # ------------------------------------------------------------------
    @staticmethod
    def _default_supports_sampling(model: Optional[str]) -> bool:
        return True

    def _supports_sampling_params(self, model: Optional[str]) -> bool:
        if not model:
            return True
        name = model.lower()
        if name in self._model_capabilities:
            return bool(self._model_capabilities[name])
        return True

    # ------------------------------------------------------------------
    # Parameter resolution
    # ------------------------------------------------------------------
    def _resolve_params(self, cfg: Dict[str, Any]) -> tuple[str, Optional[float], int]:
        model_name = cfg.get("model", self.model)
        temperature = cfg.get("temperature", self.temperature)
        if temperature is not None:
            # Anthropic accepts temperature in [0, 1]; clamp defensively.
            temperature = max(0.0, min(1.0, float(temperature)))
        max_output = cfg.get("max_output_tokens", self.max_tokens) or _DEFAULT_MAX_TOKENS
        return model_name, temperature, int(max_output)

    def _create(
        self,
        *,
        model: str,
        system: str,
        user_prompt: str,
        max_tokens: int,
        temperature: Optional[float],
        force_json: bool,
    ) -> Any:
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system or "",
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if force_json:
            kwargs["tools"] = [_EMIT_TOOL]
            kwargs["tool_choice"] = _FORCE_EMIT
        try:
            return self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:  # pragma: no cover - runtime safeguard
            raise LlmParsingError(f"Anthropic-API-Fehler: {exc}") from exc

    @staticmethod
    def _response_log(response: Any) -> Any:
        try:
            return response.model_dump()
        except Exception:  # pragma: no cover - best effort logging
            return {"repr": str(response)}

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts = [
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ]
        return "".join(parts).strip()

    @staticmethod
    def _extract_tool_payload(response: Any) -> Optional[Dict[str, Any]]:
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "emit":
                payload = getattr(block, "input", None)
                if isinstance(payload, dict):
                    return dict(payload)
        return None

    # ------------------------------------------------------------------
    # Public API (mirrors OpenAiClient)
    # ------------------------------------------------------------------
    def run(self, request: LlmRequest, llm_config: Optional[Dict[str, Any]] = None) -> Recipe:
        source_name = Path(request.source).name if request.source else "unbekannt"
        replacements = {
            "filename": source_name,
            "servings": "",
            "title_hint": Path(request.source).stem if request.source else "",
            "text": request.text,
        }
        prompt_cfg = resolve_prompt("analysis", request.locale, replacements=replacements)
        system_prompt = prompt_cfg.get("system") or _DEFAULT_ANALYSIS_SYSTEM
        user_prompt = _build_analysis_user_prompt(
            prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""), request
        )

        model_name, temperature, max_tokens = self._resolve_params(llm_config or {})
        stem = log_prompt_messages(
            "analysis",
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        response = self._create(
            model=model_name,
            system=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            force_json=True,
        )
        log_prompt_response("analysis", self._response_log(response), stem=stem)

        recipe_dict = self._extract_tool_payload(response)
        if recipe_dict is None:
            raise LlmParsingError("Claude lieferte kein strukturiertes Rezept (kein tool_use-Block)")

        _ensure_title(recipe_dict, request)
        recipe = Recipe.parse_obj(recipe_dict)
        if request.source and not recipe.metadata.source:
            recipe.metadata.source = str(request.source)
        return recipe

    def run_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> str:
        model_name, temperature, max_tokens = self._resolve_params(llm_config or {})
        stem = log_prompt_messages(
            "generic_text",
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        response = self._create(
            model=model_name,
            system=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            force_json=False,
        )
        try:
            log_prompt_response("generic_text", self._response_log(response), stem=stem)
        except Exception:  # pragma: no cover - best effort
            logger.debug("Could not log response for generic_text")
        return self._extract_text(response)

    def run_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        model_name, temperature, max_tokens = self._resolve_params(llm_config or {})
        stem = log_prompt_messages(
            "generic_json",
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        response = self._create(
            model=model_name,
            system=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            force_json=True,
        )
        log_prompt_response("generic_json", self._response_log(response), stem=stem)
        payload = self._extract_tool_payload(response)
        if payload is None:
            raise LlmParsingError("Claude-Antwort enthielt keinen tool_use-Block")
        return payload


def _fallback_title(request: LlmRequest) -> str:
    if request.title_hint and request.title_hint.strip() and request.title_hint.strip().lower() != "unbekannt":
        return request.title_hint.strip()
    if request.source:
        stem = request.source.stem
        if stem:
            return stem
    return "Rezept"


def _ensure_title(payload: Dict[str, Any], request: LlmRequest) -> None:
    title = payload.get("title")
    if isinstance(title, str) and title.strip():
        payload["title"] = title.strip()
        return
    fallback = _fallback_title(request)
    payload["title"] = fallback
    logger.warning("Claude lieferte keinen Titel – Fallback '%s' wird gesetzt", fallback)
