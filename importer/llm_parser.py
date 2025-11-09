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

logger = logging.getLogger(__name__)


class LlmParsingError(RuntimeError):
    """Raised when the LLM cannot produce a valid recipe."""


@dataclass
class LlmRequest:
    text: str
    source: Optional[Path]
    title_hint: Optional[str]
    servings_hint: Optional[str]


_JSON_PREFIX_RE = re.compile(r"```json\s*(?P<body>.+?)```", re.DOTALL)


_SYSTEM_PROMPT = """
Du bist ein hilfreicher Assistent, der Rezepttexte in eine strukturierte JSON-Darstellung für die App Mealie
überführt. Arbeite sorgfältig, beachte Mengenangaben und Einheiten und entferne Werbetexte, Footer sowie
unzusammenhängende Sätze.

Regeln:
1. Antworte ausschließlich mit gültigem JSON ohne zusätzlichen Text oder Kommentare.
2. Verwende Dezimalzahlen mit Punkt als Trenner (z.B. 0.5).
3. Zutaten werden in Abschnitte gruppiert (häufig nur ein Abschnitt ohne Namen). Jede Zutat enthält Felder:
   "name", optional "quantity" (float), optional "unit", optional "note".
4. Schritte werden nummeriert, jeder Schritt enthält ein Feld "order" (int) und "instruction" (string).
5. Füge falls möglich "recipeServings" (float), "recipeYieldQuantity" (float), "recipeYield" (Text), "totalTime", "prepTime" und "performTime" (jeweils Text wie "50 Min." oder "1,5 Stunden") sowie "notes" hinzu.
6. Fülle "metadata" mit "source" (falls bekannt) und sinnvollen "tags" oder "categories".
7. Verwende keine Abkürzungen wie "n. B." – schreibe sie aus.
8. Wenn Informationen fehlen, lasse die Felder auf null oder leeren Listen.
9. Erstelle im Feld "description" eine appetitanregende Zusammenfassung mit 2-3 vollständigen Sätzen.
""".strip()


_USER_PROMPT_TEMPLATE = """
Erzeuge JSON mit folgendem Schema:
{{
  "title": "string",
  "description": "string" | null,
  "recipeServings": float | null,
  "recipeYieldQuantity": float | null,
  "recipeYield": "string" | null,
  "totalTime": "string" | null,
  "prepTime": "string" | null,
  "performTime": "string" | null,
  "ingredients": [
    {{
      "name": "string" | null,
      "ingredients": [
        {{
          "name": "string",
          "quantity": float | null,
          "unit": "string" | null,
          "note": "string" | null
        }}
      ]
    }}
  ],
  "instructions": [
    {{
      "name": "string" | null,
      "steps": [
        {{
          "order": int,
          "instruction": "string",
          "timer_minutes": int | null
        }}
      ]
    }}
  ],
  "notes": "string" | null,
  "image_path": null,
  "image_url": null,
  "metadata": {{
    "source": "string" | null,
    "categories": ["string"],
    "cuisine": "string" | null,
    "tags": ["string"]
  }}
}}

Kontext:
- Titel-Hinweis: {title_hint}
- Dateiname: {filename}
- Hinweis Portionen: {servings}

Rezepttext:
---
{text}
---
""".strip()


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
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def run(self, request: LlmRequest) -> Recipe:
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _USER_PROMPT_TEMPLATE.format(
                        filename=str(request.source) if request.source else "unbekannt",
                        servings=request.servings_hint or "unbekannt",
                        title_hint=request.title_hint or "unbekannt",
                        text=request.text,
                    ),
                },
            ],
        }

        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_completion_tokens"] = self.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        endpoint = f"{self.base_url}/chat/completions"

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - runtime safeguard
            raise LlmParsingError(f"HTTP-Anfrage an OpenAI fehlgeschlagen: {exc}") from exc

        if response.status_code >= 400:
            raise LlmParsingError(
                f"OpenAI-API meldet Fehler {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        logger.debug("LLM response JSON: %s", data)
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover - defensive
            raise LlmParsingError("Ungewöhnliche Antwortstruktur von OpenAI") from exc

        logger.debug("LLM message payload: %s", message)

        content = _extract_message_text(message)
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
        recipe_dict = _parse_json_response(content or "")
        self._ensure_title(recipe_dict, request)
        recipe = Recipe.parse_obj(recipe_dict)

        if request.source and not recipe.metadata.source:
            recipe.metadata.source = str(request.source)

        return recipe

    def run_text(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw text response for lightweight prompts."""

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_completion_tokens"] = self.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return ""
        return content or ""

    def run_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Return parsed JSON response using OpenAI's JSON mode."""

        payload: Dict[str, Any] = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.max_tokens is not None:
            payload["max_completion_tokens"] = self.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        response = httpx.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
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
) -> Recipe:
    """Parse *text* using the provided LLM client and return a Recipe."""
    cleaned_text = text.strip()
    if not cleaned_text:
        raise LlmParsingError("Leerer Rezepttext – prüfe die PDF-Extraktion")

    request = LlmRequest(
        text=cleaned_text,
        source=source,
        title_hint=title_hint,
        servings_hint=servings_hint,
    )

    logger.debug("Sende %s Zeichen an das LLM", len(cleaned_text))
    return llm_client.run(request)


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
