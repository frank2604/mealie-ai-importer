"""Analyse recipe text with an LLM and store the structured result."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from ..context import PipelineContext, build_recipe_data_payload, auto_link_ingredients_to_instructions
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
        raw_payload = recipe.dict(by_alias=True, exclude_none=True)
        # Build RecipeData payload and pre-fill instruction->ingredient links (LLM first, fallback heuristics).
        recipe_payload = build_recipe_data_payload(recipe)
        linked_payload = self._link_ingredients_with_llm(recipe_payload)
        if linked_payload:
            logger.info("LLM ingredient linking succeeded")
        else:
            logger.info("LLM ingredient linking missing/failed, using heuristic fallback")
        recipe_payload = linked_payload or auto_link_ingredients_to_instructions(recipe_payload)
        # Keep a normalized recipe model for downstream modules
        try:
            from ..context import normalize_recipe_payload
            normalized = normalize_recipe_payload(recipe_payload)
            context.recipe = Recipe.parse_obj(normalized)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Could not hydrate linked payload back into Recipe model: %s", exc)
        raw_payload_text = json.dumps(raw_payload, ensure_ascii=False, indent=2)
        recipe_payload_text = json.dumps(recipe_payload, ensure_ascii=False, indent=2)
        raw_path: Optional[Path] = None
        recipe_path: Optional[Path] = None

        if recorder:
            raw_path = recorder.write_json("RecipeRawData", raw_payload)
            recipe_path = recorder.write_json("RecipeData", recipe_payload)
            context.recipe_data_path = recipe_path
        else:
            raw_path = context.output_dir / "RecipeRawData.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(raw_payload_text, encoding="utf-8")

            recipe_target = requested_output or (context.output_dir / "RecipeData.json")
            recipe_target.parent.mkdir(parents=True, exist_ok=True)
            recipe_target.write_text(recipe_payload_text, encoding="utf-8")
            recipe_path = recipe_target
            context.recipe_data_path = recipe_path

        final_output = recipe_path
        if requested_output and recipe_path and requested_output != recipe_path:
            requested_output.parent.mkdir(parents=True, exist_ok=True)
            requested_output.write_text(recipe_payload_text, encoding="utf-8")
            final_output = requested_output
        elif not final_output:
            final_output = recipe_path

        if raw_path:
            logger.info("Saved the raw recipe snapshot to %s", raw_path)
        if recipe_path:
            logger.info("Saved RecipeData.json to %s", recipe_path)
        if final_output:
            context.recipe_output_path = final_output
            if final_output != recipe_path:
                logger.info("Copied RecipeData.json to %s", final_output)

    def _link_ingredients_with_llm(self, recipe_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ask the LLM to map ingredients to instructions; return updated payload or None on failure."""
        if not self._llm_config.api_key:
            return None
        try:
            ingredients: List[Dict[str, str]] = []
            for section in recipe_payload.get("ingredients") or []:
                for item in section.get("ingredients") or []:
                    ing_id = item.get("id")
                    food = item.get("food") or {}
                    if not ing_id:
                        continue
                    candidates = [
                        food.get("name"),
                        food.get("originalName"),
                        item.get("name"),
                    ]
                    name = next((c for c in candidates if isinstance(c, str) and c.strip()), "")
                    ingredients.append({"id": ing_id, "name": name})
            steps: List[Dict[str, str]] = []
            for section in recipe_payload.get("instructions") or []:
                for step in section.get("steps") or []:
                    step_id = step.get("id")
                    if not step_id:
                        continue
                    steps.append(
                        {
                            "id": step_id,
                            "text": step.get("instruction") or "",
                        }
                    )
            if not ingredients or not steps:
                return None

            system_prompt = (
                "Du ordnest Zutaten den Zubereitungsschritten zu. "
                "Gib JSON mit Feld 'links': [{stepId, ingredientIds[]}]. "
                "Nutze nur die gelieferten IDs; keine Freitext-Beschreibungen. "
                "Lasse ein Feld leer, wenn nichts passt."
            )
            user_prompt = {
                "ingredients": ingredients,
                "steps": steps,
            }
            payload = {
                "model": self._llm_config.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
                ],
                "temperature": 0,
            }
            headers = {
                "Authorization": f"Bearer {self._llm_config.api_key}",
                "Content-Type": "application/json",
            }
            endpoint = f"{self._client.base_url}/chat/completions"
            response = httpx.post(endpoint, headers=headers, json=payload, timeout=self._client.timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            if not content:
                return None
            parsed = json.loads(content)
            links = parsed.get("links") if isinstance(parsed, dict) else None
            if not isinstance(links, list):
                return None
            recipe = deepcopy(recipe_payload)
            mapping: Dict[str, List[str]] = {}
            for link in links:
                if not isinstance(link, dict):
                    continue
                step_id = link.get("stepId")
                ing_ids = link.get("ingredientIds") if isinstance(link.get("ingredientIds"), list) else []
                if not step_id:
                    continue
                mapping[step_id] = [str(x) for x in ing_ids if isinstance(x, (str, int))]
            if not mapping:
                return None

            matched_steps = 0
            for section in recipe.get("instructions") or []:
                for step in section.get("steps") or []:
                    sid = step.get("id")
                    if sid and sid in mapping:
                        step["ingredientIds"] = mapping[sid]
                        matched_steps += 1
            logger.info(
                "LLM ingredient linking: %d ingredients, %d steps, %d steps matched",
                len(ingredients),
                len(steps),
                matched_steps,
            )
            return recipe
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("LLM ingredient linking failed, falling back to heuristics: %s", exc)
            return None

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

        base_dir = output_dir

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
        image_payload = {
            "fileName": image_path.name,
            "dataUrl": prepared.data_url,
            "title": recipe.title or context.source_pdf.stem,
            "description": recipe.description,
        }
        if context.pipeline_recorder:
            image_data_file = context.pipeline_recorder.write_json("RecipeImage", image_payload)
        else:
            image_data_file = base_dir / "RecipeImage.json"
            image_data_file.parent.mkdir(parents=True, exist_ok=True)
            image_data_file.write_text(json.dumps(image_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        try:
            data_reference = str(image_data_file.relative_to(base_dir))
        except ValueError:
            data_reference = str(image_data_file)

        recipe.assets.append(
            RecipeAsset(
                file_name=image_path.name,
                data=prepared.data_url,
                title=recipe.title or context.source_pdf.stem,
                description=recipe.description,
                data_path=data_reference,
            )
        )
        logger.info("Stored the selected image at %s", image_path)
