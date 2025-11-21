"""Link ingredients to instructions using the configured LLM prompt."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional

import httpx

from ..context import PipelineContext, auto_link_ingredients_to_instructions, normalize_recipe_payload
from ...config import LlmConfig
from ...llm_parser import OpenAiClient
from ...prompt_store import get_prompt_defaults, load_prompts

logger = logging.getLogger("Instruction Linking")


class InstructionLinkingModule:
    """Assign ingredients to instructions via LLM with heuristic fallback."""

    name = "Instruction Linking"

    def __init__(self, *, llm_client: Optional[OpenAiClient], llm_config: LlmConfig) -> None:
        self._client = llm_client
        self._llm_config = llm_config

    def run(self, context: PipelineContext) -> None:
        target_path = context.recipe_output_path or context.recipe_data_path
        if not target_path or not target_path.exists():
            logger.info("RecipeData.json fehlt – Schritt-Zuordnungen werden übersprungen.")
            return

        try:
            payload = json.loads(target_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Konnte RecipeData.json nicht lesen (%s) – Schritt-Zuordnungen werden übersprungen.", exc)
            return

        recipe_payload = normalize_recipe_payload(payload)

        locale = (context.config.processing.language or "de").split("-")[0]
        linked_payload = self._link_with_llm(recipe_payload, locale)
        if linked_payload is None:
            logger.info("LLM-Zuordnung nicht verfügbar – verwende heuristische Zuordnung.")
            linked_payload = auto_link_ingredients_to_instructions(recipe_payload)

        target_path.write_text(json.dumps(linked_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------
    def _link_with_llm(self, recipe_payload: Dict[str, Any], locale: str) -> Optional[Dict[str, Any]]:
        if not self._llm_config.api_key or not self._client:
            return None

        ingredients = self._collect_ingredients(recipe_payload)
        steps = self._collect_steps(recipe_payload)
        if not ingredients or not steps:
            return None

        prompt_cfg = self._resolve_prompt(locale)
        system_prompt = prompt_cfg["system"]
        free_template = prompt_cfg["free"]
        user_prompt = (
            free_template.replace("{ingredients}", json.dumps(ingredients, ensure_ascii=False))
            .replace("{steps}", json.dumps(steps, ensure_ascii=False))
            .replace("\\n", "\n")
        )

        payload = {
            "model": self._llm_config.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }

        headers = {
            "Authorization": f"Bearer {self._llm_config.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self._client.base_url}/chat/completions"

        try:
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=self._client.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("LLM-Anfrage für Schritt-Zuordnungen fehlgeschlagen: %s", exc)
            return None

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
        if not content:
            return None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM-Antwort konnte nicht gelesen werden: %s", content[:200])
            return None

        links = parsed.get("links")
        if not isinstance(links, list):
            return None

        mapping: Dict[str, List[str]] = {}
        for link in links:
            if not isinstance(link, dict):
                continue
            step_id = link.get("stepId")
            ingredient_ids = link.get("ingredientIds")
            if not step_id or not isinstance(ingredient_ids, list):
                continue
            mapping[str(step_id)] = [str(value) for value in ingredient_ids if isinstance(value, (str, int))]

        if not mapping:
            return None

        recipe = deepcopy(recipe_payload)
        matched_steps = 0
        for section in recipe.get("instructions") or []:
            for step in section.get("steps") or []:
                sid = step.get("id")
                if sid and sid in mapping:
                    step["ingredientIds"] = mapping[sid]
                    matched_steps += 1

        logger.info(
            "LLM ingredient linking: %d Zutaten, %d Schritte, %d Schritte mit Zuordnung",
            len(ingredients),
            len(steps),
            matched_steps,
        )
        return recipe

    def _collect_ingredients(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        for section in payload.get("ingredients") or []:
            for entry in section.get("ingredients") or []:
                ing_id = entry.get("id")
                if not ing_id:
                    continue
                food = entry.get("food") or {}
                candidates = [
                    food.get("name"),
                    food.get("originalName"),
                    entry.get("name"),
                ]
                name = next((c for c in candidates if isinstance(c, str) and c.strip()), "")
                items.append({"id": ing_id, "name": name})
        return items

    def _collect_steps(self, payload: Dict[str, Any]) -> List[Dict[str, str]]:
        steps: List[Dict[str, str]] = []
        for section in payload.get("instructions") or []:
            for entry in section.get("steps") or []:
                step_id = entry.get("id")
                if not step_id:
                    continue
                steps.append(
                    {
                        "id": step_id,
                        "text": entry.get("instruction") or "",
                    }
                )
        return steps

    def _resolve_prompt(self, locale: str) -> Dict[str, str]:
        prompts = load_prompts()
        defaults = get_prompt_defaults()

        candidates = [
            locale,
            locale.split("-")[0],
            "de",
            "en",
        ]

        for key in candidates:
            prompt = prompts.get(key, {})
            module = prompt.get("instructions")
            if module and module.get("system"):
                return {
                    "free": module.get("free") or defaults.get(key, {}).get("instructions", {}).get("free") or "",
                    "system": module.get("system") or defaults.get(key, {}).get("instructions", {}).get("system") or "",
                }

        default_locale = defaults.get("de") or next(iter(defaults.values()))
        return {
            "free": default_locale.get("instructions", {}).get("free", ""),
            "system": default_locale.get("instructions", {}).get("system", ""),
        }
