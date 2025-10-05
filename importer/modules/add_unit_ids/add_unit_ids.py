"""Apply resolved unit IDs to the recipe structure."""
from __future__ import annotations

import logging

from ..context import PipelineContext

logger = logging.getLogger(__name__)


class AddUnitIdsModule:
    """Write the resolved unit IDs back into the recipe JSON."""

    name = "Add Unit-IDs"

    def run(self, context: PipelineContext) -> None:
        context.ensure_recipe()
        matches = context.unit_matches
        if not matches and not context.created_unit_ids:
            logger.info("Keine Einheiten-Zuordnungen zu aktualisieren")
            return

        updated = 0
        for ref in context.iter_ingredients():
            match = matches.get(ref.key)
            if match and ref.ingredient.mealie_unit_id != match:
                ref.ingredient.mealie_unit_id = match
                updated += 1

        if updated:
            context.update_recipe_file()
            logger.info("%s Zutaten um Mealie-Einheits-ID ergänzt", updated)
        else:
            logger.info("Einheits-IDs waren bereits gesetzt")

