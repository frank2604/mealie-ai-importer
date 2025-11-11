"""Create missing foods via the Mealie API."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..context import IngredientRef, PipelineContext
from ...services.ingredients import IngredientService
from ...services.run_workspace import ApiLabel, ApiPayloadRecorder

logger = logging.getLogger("Create Foods")


_FOOD_API_LABELS: Dict[str, ApiLabel] = {
    "post_food_request": ApiLabel(
        "POST",
        "/api/foods",
        "request",
        "ingredient",
        action_template='Creating new food "{entity}" in Mealie',
    ),
    "post_food_response": ApiLabel(
        "POST",
        "/api/foods",
        "response",
        "ingredient",
        action_template='Mealie confirmed the new food "{entity}"',
    ),
    "post_food_response_error": ApiLabel(
        "POST",
        "/api/foods",
        "response_error",
        "ingredient",
        action_template='Mealie reported a problem while creating "{entity}"',
    ),
}


class CreateFoodsModule:
    """Ensure that all ingredients have matching Mealie foods."""

    name = "Create Foods"

    def __init__(self, ingredient_service: Optional[IngredientService], *, dry_run: bool = False) -> None:
        self._service = ingredient_service
        self._dry_run = dry_run

    def run(self, context: PipelineContext) -> None:
        if self._dry_run:
            logger.info(
                "Dry-run is enabled, so no foods are created automatically (%s ingredient%s still need a match)",
                len(context.missing_food_refs),
                "" if len(context.missing_food_refs) == 1 else "s",
            )
            return

        if not self._service:
            if context.missing_food_refs:
                logger.warning(
                    "Cannot contact Mealie right now. %s ingredient%s still need a food.",
                    len(context.missing_food_refs),
                    "" if len(context.missing_food_refs) == 1 else "s",
                )
            else:
                logger.debug("Skipping automatic food creation because no Mealie connection is available")
            return

        context.ensure_recipe()
        missing_refs = list(context.missing_food_refs)
        if not missing_refs:
            logger.info("Every ingredient already has a matching Mealie food")
            return

        recorder = ApiPayloadRecorder(
            recorder=context.pipeline_recorder,
            logger=logger,
            label_prefix="Mealie",
            mapping=_FOOD_API_LABELS,
            fallback_dir=context.output_dir / "create_foods_debug",
        )
        recorder.write(
            "missing_foods_initial",
            {
                "items": [ref.ingredient.name for ref in missing_refs],
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        created: Dict[str, str] = {}
        remaining: List[IngredientRef] = []
        decisions = context.food_decisions or {}

        manual_creations: List[tuple[IngredientRef, Dict[str, object]]] = []
        unresolved_refs: List[IngredientRef] = []

        for ref in missing_refs:
            decision = decisions.get(ref.key, {})
            action = str(decision.get("action", "auto")).lower()

            if action == "use_existing":
                use_food_id = decision.get("use_food_id")
                if use_food_id:
                    food_id = str(use_food_id)
                    context.food_matches[ref.key] = food_id
                    created[ref.key] = food_id
                    context.created_food_ids[ref.ingredient.name] = food_id
                    logger.info(
                        'Reusing the existing Mealie food "%s" for ingredient "%s"',
                        food_id,
                        ref.ingredient.name,
                    )
                    continue

            if action == "create":
                create_payload = decision.get("create") or {}
                if isinstance(create_payload, dict):
                    manual_creations.append((ref, create_payload))
                    continue

            if action == "skip":
                logger.info(
                    'Skipping ingredient "%s" because you chose to handle it manually',
                    ref.ingredient.name,
                )
                continue

            unresolved_refs.append(ref)

        # handle manual creations before automatic flow
        for ref, create_payload in manual_creations:
            ingredient = ref.ingredient
            try:
                resource = self._service.create_food_manual(
                    name_singular=create_payload.get("nameSingular") or ingredient.name,
                    name_plural=create_payload.get("namePlural") or ingredient.name,
                    category_id=create_payload.get("categoryId"),
                    aliases=create_payload.get("aliases") or [],
                    description=create_payload.get("description") or "",
                    debug=recorder,
                )
            except Exception as exc:  # pragma: no cover - external API failure
                logger.error(
                    'We could not create the food "%s" with the details you provided: %s',
                    ingredient.name,
                    exc,
                )
                remaining.append(ref)
                continue

            context.food_matches[ref.key] = resource.id
            context.created_food_ids[ingredient.name] = resource.id
            created[ref.key] = resource.id
            logger.info(
                'Created the food "%s" with your details (ID: %s)',
                ingredient.name,
                resource.id,
            )

        if unresolved_refs:
            names = ", ".join(ref.ingredient.name for ref in unresolved_refs)
            logger.error(
                "Die folgenden Zutaten besitzen nach dem Review noch keine Mealie-ID: %s. "
                "Bitte passe die Review-Dateien an und starte die Übertragung erneut.",
                names,
            )
            context.missing_food_refs = unresolved_refs + remaining
            raise RuntimeError("Es fehlen noch Food-Entscheidungen – Übertragung abgebrochen.")

        context.missing_food_refs = remaining
        if created:
            logger.info(
                "Created %s new food%s in Mealie",
                len(created),
                "" if len(created) == 1 else "s",
            )
            self._write_updated_cache(context)
        else:
            logger.info("No new foods were needed this time")
        recorder.write(
            "create_foods_summary",
            {
                "created": created,
                "remaining": [ref.ingredient.name for ref in remaining],
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def _write_updated_cache(self, context: PipelineContext) -> None:
        if not self._service:
            return
        timestamp = datetime.utcnow().isoformat()
        foods_payload = {
            "updated_at": timestamp,
            "foods": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "pluralName": item.get("pluralName"),
                    "aliases": item.get("aliases", []),
                }
                for item in self._service.list_foods()
            ],
        }
        context.cache_paths.foods_cache.write_text(
            json.dumps(foods_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        categories_payload = {
            "updated_at": timestamp,
            "categories": list(self._service.list_food_categories()),
        }
        context.cache_paths.food_categories_cache.write_text(
            json.dumps(categories_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
