"""Large language model integration for recipe extraction."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from .models import Recipe
from .prompt_store import resolve_prompt
from .prompt_logging import log_prompt_messages, log_prompt_response

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


_JSON_PREFIX_RE = re.compile(r"```json\s*(?P<body>.+?)```", re.DOTALL)

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


class OpenAiClient:
    """Minimal HTTP-Client für die OpenAI Chat API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 120.0,
        model_capabilities: Optional[Dict[str, bool]] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._model_capabilities = {k.lower(): v for k, v in (model_capabilities or {}).items()}

    @staticmethod
    def _default_supports_sampling(model: Optional[str]) -> bool:
        """Default-Fallback: wenn Modell unbekannt ist, Sampling zulassen."""
        if not model:
            return True
        return True

    def _supports_sampling_params(self, model: Optional[str]) -> bool:
        if not model:
            return self._default_supports_sampling(model)
        name = model.lower()
        if name in self._model_capabilities:
            return bool(self._model_capabilities[name])
        return self._default_supports_sampling(model)

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
        user_prompt = _build_analysis_user_prompt(prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""), request)

        cfg = llm_config or {}
        model_name = cfg.get("model", self.model)
        payload = {
            "model": model_name,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        temperature = cfg.get("temperature", self.temperature)
        top_p = cfg.get("top_p", None)
        max_output_tokens = cfg.get("max_output_tokens", self.max_tokens)
        supports_sampling = self._supports_sampling_params(model_name)
        if temperature is not None and supports_sampling:
            payload["temperature"] = temperature
        if top_p is not None and supports_sampling:
            payload["top_p"] = top_p
        if max_output_tokens is not None:
            payload["max_completion_tokens"] = max_output_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/chat/completions"

        stem = log_prompt_messages("analysis", payload["messages"])

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - runtime safeguard
            raise LlmParsingError(f"HTTP-Anfrage an OpenAI fehlgeschlagen: {exc}") from exc

        if response.status_code >= 400:
            raise LlmParsingError(
                f"OpenAI-API meldet Fehler {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        log_prompt_response("analysis", data, stem=stem)
        logger.debug("LLM response JSON: %s", data)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
            logger.warning("LLM full response (truncated): %s", json.dumps(data, ensure_ascii=False)[:2000])
            raise LlmParsingError("Ungewöhnliche Antwortstruktur von OpenAI") from exc

        logger.debug("LLM message payload: %s", message)

        content = _extract_message_text(message)
        if content is None:
            logger.warning("LLM full response (truncated): %s", json.dumps(data, ensure_ascii=False)[:2000])
            try:
                raw_choice = json.dumps(data.get("choices", [])[0], ensure_ascii=False)
            except Exception:  # pragma: no cover - defensive
                raw_choice = str(data.get("choices", [])[0]) if data.get("choices") else ""
            logger.warning("LLM content empty; raw choice (truncated): %s", raw_choice[:500])
        if content is None:
            parsed_payload = message.get("parsed")
            if isinstance(parsed_payload, dict):
                self._ensure_title(parsed_payload, request)
                recipe = Recipe.parse_obj(parsed_payload)
                if request.source and not recipe.metadata.source:
                    recipe.metadata.source = str(request.source)
                return recipe
            if isinstance(parsed_payload, str):
                content = parsed_payload

        logger.debug("LLM raw response: %s", content)
        try:
            recipe_dict = _parse_json_response(content or "")
        except LlmParsingError:
            logger.warning("LLM raw response (truncated): %s", (content or "")[:400])
            raise
        self._ensure_title(recipe_dict, request)
        recipe = Recipe.parse_obj(recipe_dict)

        if request.source and not recipe.metadata.source:
            recipe.metadata.source = str(request.source)

        return recipe

    def run_text(self, system_prompt: str, user_prompt: str, *, llm_config: Optional[Dict[str, Any]] = None) -> str:
        """Return raw text response for lightweight prompts."""

        cfg = llm_config or {}
        model_name = cfg.get("model", self.model)

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        temperature = cfg.get("temperature", self.temperature)
        top_p = cfg.get("top_p", None)
        max_output_tokens = cfg.get("max_output_tokens", self.max_tokens)
        supports_sampling = self._supports_sampling_params(model_name)
        if temperature is not None and supports_sampling:
            payload["temperature"] = temperature
        if top_p is not None and supports_sampling:
            payload["top_p"] = top_p
        if max_output_tokens is not None:
            payload["max_completion_tokens"] = max_output_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        stem = log_prompt_messages("generic_text", payload["messages"])

        response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)

        response.raise_for_status()
        try:
            log_prompt_response("generic_text", response.json(), stem=stem)
        except Exception:
            logger.debug("Could not log response for generic_text")
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        return content or ""

    def run_json(self, system_prompt: str, user_prompt: str, *, llm_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return parsed JSON response using OpenAI's JSON mode."""

        cfg = llm_config or {}
        model_name = cfg.get("model", self.model)

        payload: Dict[str, Any] = {
            "model": model_name,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        temperature = cfg.get("temperature", self.temperature)
        top_p = cfg.get("top_p", None)
        max_output_tokens = cfg.get("max_output_tokens", self.max_tokens)
        supports_sampling = self._supports_sampling_params(model_name)
        if temperature is not None and supports_sampling:
            payload["temperature"] = temperature
        if top_p is not None and supports_sampling:
            payload["top_p"] = top_p
        if max_output_tokens is not None:
            payload["max_completion_tokens"] = max_output_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        stem = log_prompt_messages("generic_json", payload["messages"])

        response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        log_prompt_response("generic_json", data, stem=stem)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmParsingError("Ungewöhnliche Antwortstruktur von OpenAI") from exc

        parsed = message.get("parsed")
        if isinstance(parsed, dict):
            return parsed

        content = _extract_message_text(message)
        if not content:
            raise LlmParsingError("LLM-Antwort enthält kein JSON")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmParsingError(f"Ungültiges JSON vom LLM: {exc}") from exc

    def _ensure_title(self, payload: Dict[str, Any], request: LlmRequest) -> None:
        title = payload.get("title")
        if isinstance(title, str):
            stripped = title.strip()
            if stripped:
                payload["title"] = stripped
                return
        fallback = self._fallback_title(request)
        payload["title"] = fallback
        logger.warning("LLM lieferte keinen Titel – Fallback '%s' wird gesetzt", fallback)

    @staticmethod
    def _fallback_title(request: LlmRequest) -> str:
        if request.title_hint and request.title_hint.strip() and request.title_hint.strip().lower() != "unbekannt":
            return request.title_hint.strip()
        if request.source:
            stem = request.source.stem
            if stem:
                return stem
        return "Rezept"


def _extract_message_text(message: Dict[str, Any]) -> Optional[str]:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        joined = "".join(parts).strip()
        return joined or None
    return None


def parse_with_llm(
    text: str,
    *,
    llm_client: OpenAiClient,
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


def _parse_json_response(content: str) -> Dict[str, Any]:
    candidate = content.strip()
    match = _JSON_PREFIX_RE.search(candidate)
    if match:
        candidate = match.group("body").strip()

    for snippet in _possible_json_snippets(candidate):
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            continue

    logger.debug("LLM response could not be parsed as JSON: %s", candidate)
    raise LlmParsingError(
        "LLM-Antwort war kein gültiges JSON. Aktiviere optional Debug-Logging, um den Rohtext zu prüfen."
    )


def _possible_json_snippets(text: str) -> list[str]:
    snippets = [text]
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        inner = text[start:end + 1]
        if inner not in snippets:
            snippets.append(inner)
    return snippets
