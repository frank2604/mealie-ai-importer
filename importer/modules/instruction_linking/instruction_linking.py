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
from ...prompt_store import resolve_prompt, resolve_llm_config
from ...prompt_logging import log_prompt_messages

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

        replacements = {
            "ingredients": json.dumps(ingredients, ensure_ascii=False),
            "steps": json.dumps(steps, ensure_ascii=False),
        }
        prompt_cfg = resolve_prompt("instructions", locale, replacements=replacements)
        llm_cfg = resolve_llm_config("instructions")
        logger.info(
            "LLM config (instructions): model=%s, temperature=%s, top_p=%s, max_output_tokens=%s",
            llm_cfg.get("model"),
            llm_cfg.get("temperature"),
            llm_cfg.get("top_p"),
            llm_cfg.get("max_output_tokens"),
        )
        system_prompt = prompt_cfg.get("system", "").strip()
        user_parts = [
            part.strip()
            for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
            if part and part.strip()
        ]
        user_prompt = "\n\n".join(user_parts) if user_parts else "\n\n".join(replacements.values())

        # Nutzen den zentralen OpenAiClient mit passender LLM-Config
        try:
            log_prompt_messages(
                "instructions",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            response = self._client.run_json(
                system_prompt,
                user_prompt,
                llm_config=llm_cfg,
            )
            data = response
        except Exception as exc:
            logger.warning("LLM-Anfrage für Schritt-Zuordnungen fehlgeschlagen: %s", exc)
            return None

        links = data.get("links")
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
            logger.warning("LLM-Antwort enthielt keine gültigen Zuordnungen (links): %s", content[:200])
            return None

        logger.info("LLM Schritt-Zuordnung: %s Schritte mit Zuordnungen", len(mapping))

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
