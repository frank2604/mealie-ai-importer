"""Helpers for running module pipelines."""
from __future__ import annotations

import logging
from typing import Iterable, Protocol

from .context import PipelineContext

logger = logging.getLogger(__name__)


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
        for module in self._modules:
            module_name = getattr(module, "name", module.__class__.__name__)
            logger.info("Starte Modul: %s", module_name)
            module.run(context)
            logger.info("Modul %s abgeschlossen", module_name)

