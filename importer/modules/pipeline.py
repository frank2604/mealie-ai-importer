"""Helpers for running module pipelines."""
from __future__ import annotations

import logging
from typing import Iterable, Protocol

from .context import PipelineContext

logger = logging.getLogger("Pipeline")


class PipelineModule(Protocol):
    """Protocol that every module implementation follows."""

    name: str

    def run(self, context: PipelineContext) -> None:
        """Execute the module and mutate *context* in place."""


class PipelineRunner:
    """Execute a list of modules in sequence."""

    def __init__(self, modules: Iterable[PipelineModule]):
        self._modules = list(modules)

    def run(self, context: PipelineContext) -> None:
        modules = self._modules
        if not modules:
            return

        separator = "-----------------------------------------------"
        logger.info(separator)

        last_index = len(modules) - 1
        for index, module in enumerate(modules):
            module_name = getattr(module, "name", module.__class__.__name__)
            logger.info("Starting module %s", module_name)
            module.run(context)
            logger.info("Finished module %s", module_name)
            if index < last_index:
                logger.info(separator)

        logger.info(separator)
