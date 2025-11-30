"""Assign Mealie recipe categories and tags using the LLM."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..context import PipelineContext
from ...llm_parser import OpenAiClient
from ...models import OrganizerReference, Recipe
from ...prompt_store import resolve_prompt, resolve_llm_config
from ...prompt_logging import log_prompt_messages
from ...services.ingredients import IngredientService

logger = logging.getLogger("Assign Metadata")

_METADATA_SYSTEM_PROMPT = """
Du klassifizierst Rezepte für die App Mealie. Dir stehen eine Liste möglicher Rezeptkategorien
und Tag-Optionen (gruppiert nach Themen) zur Verfügung. Für jede Eingabe:

1. Wähle genau eine RecipeCategory aus der Liste. Wenn du unsicher bist, entscheide dich für die bestpassende oder allgemeinste Option (z. B. "Sonstiges"); null ist nicht erlaubt.
2. Für jede Tag-Kategorie mit verfügbaren Optionen musst du genau ein Tag auswählen, das am ehesten passt. Kategorien ohne Optionen lässt du weg.
3. Antworte ausschließlich mit gültigem JSON im folgenden Format:
{
  "recipeCategoryId": "<UUID>",
  "tags": [
    {"category": "Name der Kategorie", "tagId": "<UUID>"},
    ...
  ]
}
4. Verwende ausschließlich IDs aus der bereitgestellten Liste. Füge keine zusätzlichen Felder hinzu.
""".strip()


class AssignMetadataModule:
    """Use the LLM to assign recipe categories and tags."""

    name = "Assign Metadata"

    def __init__(
        self,
        ingredient_service: Optional[IngredientService],
        *,
        llm_client: Optional[OpenAiClient],
        locale: str = "de",
    ) -> None:
        self._service = ingredient_service
        self._llm_client = llm_client
        self._locale = locale or "de"

    def run(self, context: PipelineContext) -> None:
        recipe = context.ensure_recipe()

        categories, tags, tag_categories = self._load_reference_data(context)
        if not categories and not tags:
            logger.info("No categories or tags are available from Mealie, so we skip this step")
            return

        self._write_cache_snapshot(context, categories, tags, tag_categories)

        if not self._llm_client:
            logger.info("No assistant is configured, so the existing categories and tags stay as they are")
            return

        classification = self._classify(recipe, categories, tags, tag_categories)
        if not context.requires_user_review:
            if classification:
                self._apply_selection(recipe, classification, categories, tags)
                context.recipe = recipe
                context.update_recipe_file()
            else:
                logger.debug("No classification was returned, so the metadata stays unchanged")
            return

        self._write_review(context, recipe, categories, tags, tag_categories, classification)

    # ------------------------------------------------------------------
    # Data acquisition helpers
    # ------------------------------------------------------------------
    def _load_reference_data(
        self, context: PipelineContext
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        categories: List[Dict[str, Any]] = []
        tags: List[Dict[str, Any]] = []
        tag_categories: List[str] = []

        if self._service:
            categories = self._service.list_recipe_categories()
            tags = self._service.list_tags()
            tag_categories = self._service.list_tag_categories()

        if not categories:
            categories = self._read_cache(context.cache_paths.recipe_categories_cache, "categories")  # type: ignore[arg-type]

        if not tags:
            tags = self._read_cache(context.cache_paths.tags_cache, "tags")  # type: ignore[arg-type]

        if not tag_categories:
            tag_categories = self._read_cache(context.cache_paths.tag_categories_cache, "categories")  # type: ignore[arg-type]

        if not tag_categories and tags:
            tag_categories = self._extract_tag_categories(tags)

        return categories, tags, tag_categories

    def _read_cache(self, path, key: str) -> List:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.debug("Could not read cache %s because it is not valid JSON", path.name)
            return []
        if isinstance(payload, dict):
            values = payload.get(key)
            if isinstance(values, list):
                return values
            # some caches may use direct list under items
            if isinstance(payload.get("items"), list):
                return payload["items"]
        elif isinstance(payload, list):
            return payload
        return []

    def _write_cache_snapshot(
        self,
        context: PipelineContext,
        categories: List[Dict[str, Any]],
        tags: List[Dict[str, Any]],
        tag_categories: List[str],
    ) -> None:
        timestamp = datetime.utcnow().isoformat()
        context.cache_paths.recipe_categories_cache.write_text(
            json.dumps({"updated_at": timestamp, "categories": categories}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        context.cache_paths.tags_cache.write_text(
            json.dumps({"updated_at": timestamp, "tags": tags}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        context.cache_paths.tag_categories_cache.write_text(
            json.dumps({"updated_at": timestamp, "categories": tag_categories}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------
    def _classify(
        self,
        recipe: Recipe,
        categories: List[Dict[str, Any]],
        tags: List[Dict[str, Any]],
        tag_categories: List[str],
    ) -> Optional[Dict[str, Any]]:
        try:
            payload = self._build_llm_payload(recipe, categories, tags, tag_categories)
        except ValueError as exc:
            logger.warning("Could not prepare the classification payload: %s", exc)
            return None

        if not self._llm_client:
            logger.info("No assistant is configured, so no metadata suggestions are available")
            return None

        prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            system_prompt, user_prompt = self._build_prompts(prompt)
            llm_cfg = resolve_llm_config("metadata")
            logger.info(
                "LLM config (metadata): model=%s, temperature=%s, top_p=%s, max_output_tokens=%s",
                llm_cfg.get("model"),
                llm_cfg.get("temperature"),
                llm_cfg.get("top_p"),
                llm_cfg.get("max_output_tokens"),
            )
            log_prompt_messages(
                "metadata",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            response_text = self._llm_client.run_text(system_prompt, user_prompt, llm_config=llm_cfg)
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("The assistant request for categories failed: %s", exc)
            return None

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning("The assistant did not return valid JSON: %s", response_text[:200])
            return None

    def _build_prompts(self, payload: str) -> tuple[str, str]:
        replacements = {"payload_json": payload}
        prompt_cfg = resolve_prompt("metadata", self._locale, replacements=replacements)
        system_prompt = prompt_cfg.get("system", _METADATA_SYSTEM_PROMPT)
        user_parts = [
            part.strip()
            for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
            if part and part.strip()
        ]
        if user_parts:
            user_prompt = "\n\n".join(user_parts)
        else:
            locale_lower = self._locale.lower()
            context_label = "Context data (JSON)" if locale_lower.startswith("en") else "Kontextdaten (JSON)"
            user_prompt = f"{context_label}:\n{payload}"
        return system_prompt, user_prompt

    def _write_review(
        self,
        context: PipelineContext,
        recipe: Recipe,
        categories: List[Dict[str, Any]],
        tags: List[Dict[str, Any]],
        tag_categories: List[str],
        classification: Optional[Dict[str, Any]],
    ) -> None:
        recorder = context.pipeline_recorder
        if not recorder:
            logger.debug("No pipeline recorder available, so no metadata review file was created")
            return

        available_categories = [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "groupId": item.get("groupId"),
                "slug": item.get("slug"),
            }
            for item in categories
            if item.get("id")
        ]

        tag_groups = self._group_tags_by_category(tags, tag_categories)
        available_tag_categories = []
        iterable_groups = (
            tag_groups.items()
            if isinstance(tag_groups, dict)
            else tag_groups
        )
        for group in iterable_groups:
            if isinstance(group, dict):
                category = group.get("category")
                entries = group.get("options") or group.get("tags") or []
            else:
                try:
                    category, entries = group
                except ValueError:
                    continue
            tags_payload = []
            for tag in entries:
                if not isinstance(tag, dict) or not tag.get("id"):
                    continue
                tags_payload.append(
                    {
                        "id": str(tag.get("id") or ""),
                        "name": str(tag.get("name") or ""),
                        "detail": tag.get("detail"),
                        "groupId": tag.get("groupId") or category,
                        "slug": tag.get("slug"),
                    }
                )
            available_tag_categories.append({"category": category, "tags": tags_payload})

        current_category = None
        if recipe.metadata.mealie_categories:
            current_category = {
                "id": recipe.metadata.mealie_categories[0].id,
                "name": recipe.metadata.mealie_categories[0].name,
            }
        current_tags = [
            {"id": tag.id, "name": tag.name, "groupId": tag.group_id}
            for tag in recipe.metadata.mealie_tags
        ]

        proposal_category_id = None
        proposal_tags: List[str] = []
        if isinstance(classification, dict):
            proposal_category_id = classification.get("recipeCategoryId")
            for entry in classification.get("tags", []) or []:
                if isinstance(entry, dict) and entry.get("tagId"):
                    proposal_tags.append(str(entry.get("tagId")))

        payload = {
            "generatedAt": datetime.utcnow().isoformat(),
            "current": {
                "recipeServings": recipe.recipe_servings,
                "totalTime": recipe.total_time,
                "category": current_category,
                "tagIds": [tag["id"] for tag in current_tags],
            },
            "proposal": {
                "recipeServings": recipe.recipe_servings,
                "totalTime": recipe.total_time,
                "categoryId": proposal_category_id or (current_category or {}).get("id"),
                "tagIds": proposal_tags or [tag["id"] for tag in current_tags],
            },
            "userDecision": {
                "recipeServings": recipe.recipe_servings,
                "totalTime": recipe.total_time,
                "categoryId": proposal_category_id or (current_category or {}).get("id"),
                "tagIds": proposal_tags or [tag["id"] for tag in current_tags],
            },
            "available": {
                "categories": available_categories,
                "tagCategories": available_tag_categories,
            },
            "instructions": (
                "Update 'userDecision' to change category, tags, recipeServings, or totalTime. "
                "Leave values as-is to accept the suggested data."
            ),
        }

        review_path = recorder.write_json("MetadataReview", payload)
        context.metadata_review_path = review_path
        context.metadata_decision = {}
        logger.info("Saved the metadata review to %s", review_path)

        prompt = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            system_prompt, user_prompt = self._build_prompts(prompt)
            response_text = self._llm_client.run_text(system_prompt, user_prompt)
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("The assistant request for categories failed: %s", exc)
            return None

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning("The assistant did not return valid JSON: %s", response_text[:200])
            return None

    def _build_llm_payload(
        self,
        recipe: Recipe,
        categories: List[Dict[str, Any]],
        tags: List[Dict[str, Any]],
        tag_categories: List[str],
    ) -> Dict[str, Any]:
        ingredient_items: List[Dict[str, Any]] = []
        for section in recipe.ingredients:
            for item in section.ingredients:
                ingredient_items.append(
                    {
                        "name": item.name,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "note": item.note,
                    }
                )
        ingredient_items = ingredient_items[:40]

        instruction_texts: List[str] = []
        for section in recipe.instructions:
            for step in section.steps:
                instruction_texts.append(step.instruction.strip())
        instruction_texts = instruction_texts[:10]

        tag_groups = self._group_tags_by_category(tags, tag_categories)

        return {
            "recipe": {
                "title": recipe.title,
                "description": recipe.description,
                "notes": recipe.notes,
                "recipeServings": recipe.recipe_servings,
                "totalTime": recipe.total_time,
                "ingredients": ingredient_items,
                "instructions": instruction_texts,
            },
            "foodCategories": [
                {
                    "id": str(item.get("id")),
                    "name": item.get("name"),
                    "slug": item.get("slug"),
                    "groupId": item.get("groupId"),
                }
                for item in categories
                if item.get("id") and item.get("name")
            ],
            "tagGroups": tag_groups,
        }

    def _group_tags_by_category(
        self,
        tags: Iterable[Dict[str, Any]],
        tag_categories: Iterable[str],
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, str]]] = {category: [] for category in tag_categories}
        for tag in tags:
            name = str(tag.get("name") or "")
            if not tag.get("id") or not name:
                continue
            category, detail = self._split_tag_name(name)
            category = category or ""
            grouped.setdefault(category, [])
            grouped[category].append(
                {
                    "id": str(tag.get("id")),
                    "name": name,
                    "slug": tag.get("slug"),
                    "groupId": tag.get("groupId"),
                    "detail": detail,
                }
            )

        result: List[Dict[str, Any]] = []
        for category, options in grouped.items():
            if not options:
                continue
            result.append(
                {
                    "category": category or None,
                    "options": options[:20],
                }
            )
        return result

    # ------------------------------------------------------------------
    # Result handling
    # ------------------------------------------------------------------
    def _apply_selection(
        self,
        recipe: Recipe,
        classification: Dict[str, Any],
        categories: List[Dict[str, Any]],
        tags: List[Dict[str, Any]],
    ) -> None:
        selected_categories: List[OrganizerReference] = []
        category_name_list: List[str] = []

        category_id = classification.get("recipeCategoryId")
        if category_id:
            match = self._lookup_by_id(categories, category_id)
            if match:
                selected_categories.append(
                    OrganizerReference(
                        id=str(match.get("id")),
                        name=str(match.get("name") or ""),
                        group_id=match.get("groupId"),
                        slug=match.get("slug"),
                    )
                )
                category_name_list.append(str(match.get("name") or ""))

        selected_tags: List[OrganizerReference] = []
        tag_name_list: List[str] = []
        tag_entries = classification.get("tags") or []
        for entry in tag_entries:
            if not isinstance(entry, dict):
                continue
            tag_id = entry.get("tagId") or entry.get("id")
            if not tag_id:
                continue
            match = self._lookup_by_id(tags, tag_id)
            if not match:
                continue
            selected_tags.append(
                OrganizerReference(
                    id=str(match.get("id")),
                    name=str(match.get("name") or ""),
                    group_id=match.get("groupId"),
                    slug=match.get("slug"),
                )
            )
            tag_name_list.append(str(match.get("name") or ""))

        metadata = recipe.metadata
        metadata.mealie_categories = selected_categories
        metadata.categories = [name for name in category_name_list if name]

        metadata.mealie_tags = selected_tags
        metadata.tags = [name for name in tag_name_list if name]

        cuisine_tag = next(
            (ref for ref in selected_tags if self._split_tag_name(ref.name)[0].lower() == "küche"),
            None,
        )
        if cuisine_tag:
            metadata.cuisine = self._split_tag_name(cuisine_tag.name)[1] or metadata.cuisine

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _lookup_by_id(self, items: Iterable[Dict[str, Any]], item_id: Any) -> Optional[Dict[str, Any]]:
        for item in items:
            if str(item.get("id")) == str(item_id):
                return item
        return None

    def _split_tag_name(self, name: str) -> Tuple[str, str]:
        if "|" not in name:
            return "", name.strip()
        category, detail = name.split("|", 1)
        return category.strip(), detail.strip()

    def _extract_tag_categories(self, tags: Iterable[Dict[str, Any]]) -> List[str]:
        categories: set[str] = set()
        for tag in tags:
            category, _ = self._split_tag_name(str(tag.get("name") or ""))
            if category:
                categories.add(category)
        return sorted(categories)
