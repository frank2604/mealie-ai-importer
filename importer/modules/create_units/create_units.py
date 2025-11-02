"""Create missing units in Mealie."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..context import IngredientRef, PipelineContext
from ...services.ingredients import IngredientService
from ...services.run_workspace import ApiLabel, ApiPayloadRecorder

logger = logging.getLogger("Create Units")


class CreateUnitsModule:
    """Ensure that all ingredient units exist in Mealie."""

    name = "Create Units"

    def __init__(self, ingredient_service: Optional[IngredientService], *, dry_run: bool = False) -> None:
        self._service = ingredient_service
        self._dry_run = dry_run

    def run(self, context: PipelineContext) -> None:
        if self._dry_run:
            logger.info(
                "Dry-run is enabled, so no units are created automatically (%s ingredient%s still need a match)",
                len(context.missing_unit_refs),
                "" if len(context.missing_unit_refs) == 1 else "s",
            )
            return

        if not self._service:
            if context.missing_unit_refs:
                logger.warning(
                    "Cannot contact Mealie right now. %s unit%s still need an ID.",
                    len(context.missing_unit_refs),
                    "" if len(context.missing_unit_refs) == 1 else "s",
                )
            else:
                logger.debug("Skipping automatic unit creation because no Mealie connection is available")
            return

        missing_refs = list(context.missing_unit_refs)
        if not missing_refs:
            logger.info("Every ingredient already has a matching Mealie unit")
            return

        recorder = ApiPayloadRecorder(
            recorder=context.pipeline_recorder,
            logger=logger,
            label_prefix="Mealie",
            mapping=_UNIT_API_LABELS,
            fallback_dir=context.output_dir / "create_units_debug",
        )

        created: Dict[str, str] = {}
        remaining: List[IngredientRef] = []
        decisions = context.unit_decisions or {}

        auto_refs: List[IngredientRef] = []
        manual_creations: List[tuple[IngredientRef, Dict[str, object]]] = []

        for ref in missing_refs:
            decision = decisions.get(ref.key, {})
            action = str(decision.get("action", "auto")).lower()

            if action == "use_existing":
                use_unit_id = decision.get("use_unit_id")
                if use_unit_id:
                    unit_id = str(use_unit_id)
                    context.unit_matches[ref.key] = unit_id
                    context.created_unit_ids[ref.ingredient.unit or unit_id] = unit_id
                    logger.info(
                        'Reusing the existing Mealie unit "%s" for "%s"',
                        unit_id,
                        ref.ingredient.unit or "",
                    )
                    continue

            if action == "create":
                create_payload = decision.get("create") or {}
                if isinstance(create_payload, dict):
                    manual_creations.append((ref, create_payload))
                    continue

            if action == "skip":
                logger.info(
                    'Skipping unit creation for "%s" because you chose to handle it manually',
                    ref.ingredient.unit or "",
                )
                continue

            auto_refs.append(ref)

        for ref, create_payload in manual_creations:
            unit_name = create_payload.get("name") or (ref.ingredient.unit or "")
            try:
                resource = self._service.create_unit_manual(
                    name=unit_name,
                    plural_name=create_payload.get("pluralName"),
                    abbreviation=create_payload.get("abbreviation"),
                    plural_abbreviation=create_payload.get("pluralAbbreviation"),
                    use_abbreviation=bool(create_payload.get("useAbbreviation")),
                    debug=recorder,
                )
            except Exception as exc:  # pragma: no cover - network failure
                logger.error('We could not create the unit "%s" with the details you provided: %s', unit_name, exc)
                remaining.append(ref)
                continue

            context.unit_matches[ref.key] = resource.id
            context.created_unit_ids[unit_name] = resource.id
            created[ref.key] = resource.id
            logger.info('Created the unit "%s" with your details (ID: %s)', unit_name, resource.id)

        missing_refs = auto_refs
        if missing_refs:
            logger.info(
                "Asking the assistant for unit naming ideas: %s",
                ", ".join(ref.ingredient.unit for ref in missing_refs if ref.ingredient.unit),
            )
            self._service.prepare_unit_forms(
                (ref.ingredient.unit for ref in missing_refs),
                debug=recorder,
            )

        for ref in missing_refs:
            ingredient = ref.ingredient
            unit_name = ingredient.unit or ""
            if not unit_name:
                continue
            try:
                resource = self._service.get_or_create_unit(
                    name=unit_name,
                    debug=recorder,
                )
            except Exception as exc:  # pragma: no cover - network failure
                logger.error('Mealie could not create the unit "%s": %s', unit_name, exc)
                remaining.append(ref)
                continue

            created[ref.key] = resource.id
            context.unit_matches[ref.key] = resource.id
            context.created_unit_ids[unit_name] = resource.id
            logger.info('Created "%s" in Mealie (ID: %s)', unit_name, resource.id)

        context.missing_unit_refs = remaining
        if created:
            logger.info(
                "Created %s new unit%s in Mealie",
                len(created),
                "" if len(created) == 1 else "s",
            )
            self._write_updated_cache(context)
        else:
            logger.info("No new units were needed this time")

    def _write_updated_cache(self, context: PipelineContext) -> None:
        if not self._service:
            return
        snapshot = {
            "units": [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "pluralName": item.get("pluralName"),
                    "abbreviation": item.get("abbreviation"),
                    "pluralAbbreviation": item.get("pluralAbbreviation"),
                }
                for item in self._service.list_units()
            ],
        }
        payload = {"updated_at": datetime.utcnow().isoformat(), **snapshot}
        context.cache_paths.units_cache.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
_UNIT_API_LABELS: Dict[str, ApiLabel] = {
    "post_unit_request": ApiLabel(
        "POST",
        "/api/units",
        "request",
        "name",
        action_template='Creating new unit "{entity}" in Mealie',
    ),
    "post_unit_response": ApiLabel(
        "POST",
        "/api/units",
        "response",
        "name",
        action_template='Mealie confirmed the new unit "{entity}"',
    ),
    "post_unit_response_error": ApiLabel(
        "POST",
        "/api/units",
        "response_error",
        "name",
        action_template='Mealie reported a problem while creating unit "{entity}"',
    ),
}
