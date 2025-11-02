"""Analyse recipe text with an LLM and store the structured result."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional
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

logger = logging.getLogger("AI Analyser")


class AiAnalyserModule:
    """Use an LLM to transform raw text into a structured recipe."""

    name = "AI Analyser"

    def __init__(
        self,
        *,
        llm_client: OpenAiClient,
        llm_config: LlmConfig,
        image_output_dir: Optional[Path] = None,
    ) -> None:
        self._client = llm_client
        self._llm_config = llm_config
        self._image_output_dir = image_output_dir

    def run(self, context: PipelineContext) -> None:
        extraction = context.ensure_extraction()
        logger.info("Starting the AI analysis with %s characters of recipe text", len(extraction.text))

        recipe = self._parse_recipe_with_retry(extraction, context)

        self._attach_image_assets(recipe, context)

        recorder = context.pipeline_recorder
        requested_output = context.recipe_output_path
        payload = recipe.dict(by_alias=True)
        raw_path: Optional[Path] = None
        enriched_path: Optional[Path] = None

        if recorder:
            raw_path = recorder.write_json("RecipeRawData", payload)
            enriched_path = recorder.write_json("RecipeRawDataEnriched", payload)
            context.recipe_data_path = enriched_path
            context.save_recipe(recipe, destination=enriched_path, overwrite=False)
        else:
            target = context.recipe_output_path or (context.output_dir / "RecipeRawData.json")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            context.recipe_data_path = target
            context.save_recipe(recipe, destination=target)
            raw_path = target
            enriched_path = target

        final_output = raw_path
        if requested_output and raw_path and requested_output != raw_path:
            requested_output.parent.mkdir(parents=True, exist_ok=True)
            requested_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            final_output = requested_output

        if final_output:
            context.recipe_output_path = final_output
            logger.info("Saved the structured recipe to %s", final_output)
        if enriched_path:
            logger.info("Updated RecipeRawDataEnriched.json at %s", enriched_path)

    def _parse_recipe_with_retry(self, extraction: PdfExtractionResult, context: PipelineContext) -> Recipe:
        attempts = 5
        last_error: Optional[LlmParsingError] = None
        for attempt in range(1, attempts + 1):
            try:
                return parse_with_llm(
                    extraction.text,
                    llm_client=self._client,
                    source=context.source_pdf,
                    servings_hint=context.servings_hint,
                )
            except LlmParsingError as exc:
                last_error = exc
                if attempt >= attempts or not self._is_retryable_error(exc):
                    raise RuntimeError(f"The assistant could not process the recipe: {exc}") from exc
                wait_seconds = min(2 ** (attempt - 1), 30)
                logger.warning(
                    "OpenAI request failed (attempt %s/%s): %s – retrying in %s second%s",
                    attempt,
                    attempts,
                    exc,
                    wait_seconds,
                    "" if wait_seconds == 1 else "s",
                )
                time.sleep(wait_seconds)
        assert last_error is not None  # for type checkers
        raise RuntimeError(f"The assistant could not process the recipe: {last_error}") from last_error

    @staticmethod
    def _is_retryable_error(error: LlmParsingError) -> bool:
        message = str(error).lower()
        retry_tokens = [
            "429",
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "temporarily",
            "bad gateway",
            "gateway",
        ]
        return any(token in message for token in retry_tokens)

    def _attach_image_assets(self, recipe: Recipe, context: PipelineContext) -> None:
        extraction = context.ensure_extraction()
        if not extraction.images:
            logger.debug("No images were found in the PDF")
            return

        best_image = select_best_image(extraction.images)
        if best_image is None:
            logger.debug("No suitable image was selected")
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
                logger.debug("The vision model did not provide a crop, so we use the original image")
        elif self._llm_config.api_key and crop_image_with_llm is None and _VISION_IMPORT_ERROR:
            logger.warning(
                "Could not load the vision helper (%s). Using the original image.",
                _VISION_IMPORT_ERROR,
            )
        output_dir = (
            context.pipeline_recorder.directory
            if context.pipeline_recorder
            else (self._image_output_dir or context.output_dir)
        )
        prepared = prepare_image_asset(
            image_bytes,
            base_name="image",
            output_dir=output_dir,
        )
        if not prepared:
            logger.warning("Could not convert the image for upload")
            return

        if context.pipeline_recorder:
            numbered_image = context.pipeline_recorder.copy_file(prepared.file_path, label="RecipeImage")
            if prepared.file_path != numbered_image:
                try:
                    prepared.file_path.unlink(missing_ok=True)
                except TypeError:
                    # Python < 3.8 fallback without missing_ok
                    if prepared.file_path.exists():
                        prepared.file_path.unlink()
            image_path = numbered_image
        else:
            image_path = prepared.file_path

        recipe.image_path = str(image_path)
        recipe.assets.append(
            RecipeAsset(
                file_name=image_path.name,
                data=prepared.data_url,
                title=recipe.title or context.source_pdf.stem,
            )
        )
        logger.info("Stored the selected image at %s", image_path)
