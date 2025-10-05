"""Analyse recipe text with an LLM and store the structured result."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from ..context import PipelineContext
from ...config import LlmConfig
from ...image_utils import prepare_image_asset, select_best_image
from ...llm_parser import LlmParsingError, OpenAiClient, parse_with_llm
from ...models import Recipe, RecipeAsset

try:  # pragma: no cover - optional vision dependency
    from ...vision_cropper import crop_image_with_llm
except ModuleNotFoundError as exc:  # pragma: no cover - handled gracefully
    crop_image_with_llm = None  # type: ignore[assignment]
    _VISION_IMPORT_ERROR = exc
else:
    _VISION_IMPORT_ERROR = None

logger = logging.getLogger(__name__)


class AiAnalyserModule:
    """Use an LLM to transform raw text into a structured recipe."""

    name = "AI-Analyser"

    def __init__(
        self,
        *,
        llm_client: OpenAiClient,
        llm_config: LlmConfig,
        output_json: Path,
        image_output_dir: Path,
    ) -> None:
        self._client = llm_client
        self._llm_config = llm_config
        self._output_json = output_json
        self._image_output_dir = image_output_dir

    def run(self, context: PipelineContext) -> None:
        extraction = context.ensure_extraction()
        logger.info("Starte LLM-Analyse (%s Zeichen)", len(extraction.text))

        try:
            recipe = parse_with_llm(
                extraction.text,
                llm_client=self._client,
                source=context.source_pdf,
                servings_hint=context.servings_hint,
            )
        except LlmParsingError as exc:
            raise RuntimeError(f"LLM konnte Rezept nicht verarbeiten: {exc}") from exc

        self._attach_image_assets(recipe, context)

        context.save_recipe(recipe)
        logger.info("RecipeRawData.json aktualisiert unter %s", context.cache_paths.recipe_raw)

        if self._output_json:
            self._output_json.parent.mkdir(parents=True, exist_ok=True)
            self._output_json.write_text(
                json.dumps(recipe.dict(by_alias=True), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Rezept auch nach %s geschrieben", self._output_json)

        context.recipe_output_path = self._output_json

    def _attach_image_assets(self, recipe: Recipe, context: PipelineContext) -> None:
        extraction = context.ensure_extraction()
        if not extraction.images:
            logger.debug("Keine Bilder in der PDF gefunden")
            return

        best_image = select_best_image(extraction.images)
        if best_image is None:
            logger.debug("Kein geeignetes Bild ausgewählt")
            return

        image_bytes = best_image.data
        if (
            crop_image_with_llm is not None
            and self._llm_config.api_key
            and self._llm_config.vision_model
        ):
            cropped = crop_image_with_llm(
                image_bytes,
                llm_config=self._llm_config,
                title=recipe.title or context.source_pdf.stem,
            )
            if cropped:
                image_bytes = cropped
            else:
                logger.debug("Vision-Modell lieferte keinen Zuschnitt – verwende Originalbild")
        elif self._llm_config.api_key and crop_image_with_llm is None and _VISION_IMPORT_ERROR:
            logger.warning(
                "Vision-Modul konnte nicht geladen werden (%s). Verwende Originalbild.",
                _VISION_IMPORT_ERROR,
            )

        prepared = prepare_image_asset(
            image_bytes,
            base_name=context.source_pdf.stem,
            output_dir=self._image_output_dir,
        )
        if not prepared:
            logger.warning("Bild konnte nicht konvertiert werden")
            return

        recipe.image_path = str(prepared.file_path)
        recipe.assets.append(
            RecipeAsset(
                file_name=prepared.file_path.name,
                data=prepared.data_url,
                title=recipe.title or context.source_pdf.stem,
            )
        )
        logger.info("Bild gespeichert unter %s", prepared.file_path)

