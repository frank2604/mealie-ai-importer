"""Apply resolved food IDs to the recipe structure."""
from __future__ import annotations

import logging

from ..context import PipelineContext

logger = logging.getLogger(__name__)


class AddFoodIdsModule:
    """Write the resolved food IDs back into the recipe JSON."""

    name = "Add Food-IDs"

    def run(self, context: PipelineContext) -> None:
        context.ensure_recipe()
        matches = context.food_matches
        if not matches and not context.created_food_ids:
            logger.info("Keine Lebensmittel-Zuordnungen zu aktualisieren")
            return

        updated = 0
        for ref in context.iter_ingredients():
            match = matches.get(ref.key)
            if match and ref.ingredient.mealie_food_id != match:
                ref.ingredient.mealie_food_id = match
                updated += 1

        if updated:
            context.update_recipe_file()
            logger.info("%s Zutaten um Mealie-Food-ID ergänzt", updated)
        else:
            logger.info("Lebensmittel-IDs waren bereits gesetzt")

