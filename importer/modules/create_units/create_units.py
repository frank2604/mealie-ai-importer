"""Create missing units in Mealie."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..context import IngredientRef, PipelineContext
from ...services.ingredients import IngredientService

logger = logging.getLogger(__name__)


class CreateUnitsModule:
    """Ensure that all ingredient units exist in Mealie."""

    name = "Create Units"

    def __init__(self, ingredient_service: Optional[IngredientService], *, dry_run: bool = False) -> None:
        self._service = ingredient_service
        self._dry_run = dry_run

    def run(self, context: PipelineContext) -> None:
        if self._dry_run:
            logger.info(
                "Dry-Run aktiv – Einheiten werden nicht automatisch angelegt (%s offen)",
                len(context.missing_unit_refs),
            )
            return

        if not self._service:
            if context.missing_unit_refs:
                logger.warning(
                    "Keine Verbindung zur Mealie-API. %s Einheiten bleiben ohne ID.",
                    len(context.missing_unit_refs),
                )
            else:
                logger.debug("Kein IngredientService verfügbar – überspringe Create Units")
            return

        missing_refs = list(context.missing_unit_refs)
        if not missing_refs:
            logger.info("Alle Einheiten bereits gefunden – nichts anzulegen")
            return

        created: Dict[str, str] = {}
        remaining: List[IngredientRef] = []

        for ref in missing_refs:
            ingredient = ref.ingredient
            unit_name = ingredient.unit or ""
            if not unit_name:
                continue
            try:
                resource = self._service.get_or_create_unit(
                    name=unit_name,
                    plural_name=unit_name,
                    abbreviation=unit_name,
                )
            except Exception as exc:  # pragma: no cover - network failure
                logger.error("Einheit '%s' konnte nicht angelegt werden: %s", unit_name, exc)
                remaining.append(ref)
                continue

            created[ref.key] = resource.id
            context.unit_matches[ref.key] = resource.id
            context.created_unit_ids[unit_name] = resource.id

        context.missing_unit_refs = remaining
        if created:
            logger.info("%s neue Einheiten angelegt", len(created))
            self._write_updated_cache(context)
        else:
            logger.info("Keine neuen Einheiten angelegt")

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

