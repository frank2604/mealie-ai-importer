"""Refresh local Mealie cache files via the IngredientService."""
from __future__ import annotations

import logging
from typing import Optional

from ..services.ingredients import IngredientService
from .context import PipelineContext

logger = logging.getLogger("Refresh Caches")


class RefreshCachesModule:
    """Ensure local cache files are in sync with the Mealie API."""

    name = "Refresh Mealie caches"

    def __init__(self, ingredient_service: Optional[IngredientService]) -> None:
        self._service = ingredient_service

    def run(self, context: PipelineContext) -> None:
        if not self._service:
            logger.info("Skipping this step because no connection to Mealie is available")
            return

        logger.info("Refreshing the ingredient and unit lists from Mealie")
        try:
            self._service.refresh()
        except Exception as exc:  # pragma: no cover - network failure
            logger.warning("We could not update the Mealie lists: %s", exc)
        else:
            logger.info("Finished refreshing the Mealie lists")
