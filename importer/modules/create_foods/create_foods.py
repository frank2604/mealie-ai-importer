"""Create missing foods via the Mealie API."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..context import IngredientRef, PipelineContext
from ...services.ingredients import IngredientService

logger = logging.getLogger(__name__)


class CreateFoodsModule:
    """Ensure that all ingredients have matching Mealie foods."""

    name = "Create Foods"

    def __init__(self, ingredient_service: Optional[IngredientService], *, dry_run: bool = False) -> None:
        self._service = ingredient_service
        self._dry_run = dry_run

    def run(self, context: PipelineContext) -> None:
        if self._dry_run:
            logger.info(
                "Dry-Run aktiv – Lebensmittel werden nicht automatisch angelegt (%s offen)",
                len(context.missing_food_refs),
            )
            return

        if not self._service:
            if context.missing_food_refs:
                logger.warning(
                    "Keine Verbindung zur Mealie-API. %s Lebensmittel bleiben ohne ID.",
                    len(context.missing_food_refs),
                )
            else:
                logger.debug("Kein IngredientService verfügbar – überspringe Create Foods")
            return

        recipe = context.ensure_recipe()
        missing_refs = list(context.missing_food_refs)
        if not missing_refs:
            logger.info("Alle Lebensmittel bereits gefunden – nichts anzulegen")
            return

        created: Dict[str, str] = {}
        remaining: List[IngredientRef] = []

        for ref in missing_refs:
            ingredient = ref.ingredient
            try:
                resource = self._service.get_or_create_food(
                    name=ingredient.name,
                    description=ingredient.note or "",
                    category_hint=self._category_hint(recipe),
                )
            except Exception as exc:  # pragma: no cover - external API failure
                logger.error("Lebensmittel '%s' konnte nicht angelegt werden: %s", ingredient.name, exc)
                remaining.append(ref)
                continue

            created[ref.key] = resource.id
            context.food_matches[ref.key] = resource.id
            context.created_food_ids[ingredient.name] = resource.id

        context.missing_food_refs = remaining
        if created:
            logger.info("%s neue Lebensmittel angelegt", len(created))
            self._write_updated_cache(context)
        else:
            logger.info("Keine neuen Lebensmittel angelegt")

    def _category_hint(self, recipe) -> Optional[str]:
        if recipe.metadata.categories:
            return recipe.metadata.categories[0]
        if recipe.metadata.cuisine:
            return recipe.metadata.cuisine
        return None

    def _write_updated_cache(self, context: PipelineContext) -> None:
        if not self._service:
            return
        snapshot = {
            "foods": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "pluralName": item.get("pluralName"),
                    "aliases": item.get("aliases", []),
                }
                for item in self._service.list_foods()
            ],
            "categories": list(self._service.list_food_categories()),
        }
        payload = {"updated_at": datetime.utcnow().isoformat(), **snapshot}
        context.cache_paths.foods_cache.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

