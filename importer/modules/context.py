"""Shared pipeline context and helper structures."""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from ..config import AppConfig
from ..services.run_workspace import PipelineRecorder
from ..models import Ingredient, Recipe
from ..pdf_extractor import PdfExtractionResult

logger = logging.getLogger(__name__)


def normalize_recipe_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return *payload* with legacy ingredient fields populated from enriched structures."""
    if not isinstance(payload, dict):
        return payload
    data = deepcopy(payload)
    sections = data.get("ingredients")
    if not isinstance(sections, list):
        return data
    for section in sections:
        items = section.get("ingredients")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            legacy_food_status = item.pop("foodStatus", None)
            legacy_unit_status = item.pop("unitStatus", None)
            if legacy_food_status and "foodBadgeId" not in item:
                item["foodBadgeId"] = legacy_food_status
            if legacy_unit_status and "unitBadgeId" not in item:
                item["unitBadgeId"] = legacy_unit_status
            food_block = item.pop("food", None)
            if isinstance(food_block, dict):
                name = food_block.get("name") or food_block.get("originalName")
                if name:
                    item.setdefault("name", name)
                original_name = food_block.get("originalName") or name
                if original_name:
                    item.setdefault("foodOriginalName", original_name)
                new_id = food_block.get("newId")
                if new_id is not None and "foodNewId" not in item:
                    item["foodNewId"] = new_id
                mealie_food_id = food_block.get("mealieFoodId")
                if mealie_food_id is not None:
                    item["mealieFoodId"] = mealie_food_id
                badge_id = food_block.get("badgeId")
                if badge_id is not None:
                    item["foodBadgeId"] = badge_id
            unit_block = item.pop("unit", None)
            if isinstance(unit_block, dict):
                unit_name = unit_block.get("name") or unit_block.get("originalName")
                if unit_name:
                    item.setdefault("unit", unit_name)
                original_unit = unit_block.get("originalName") or unit_name
                if original_unit:
                    item.setdefault("unitOriginalName", original_unit)
                new_unit_id = unit_block.get("newId")
                if new_unit_id is not None and "unitNewId" not in item:
                    item["unitNewId"] = new_unit_id
                mealie_unit_id = unit_block.get("mealieUnitId")
                if mealie_unit_id is not None:
                    item["mealieUnitId"] = mealie_unit_id
                badge_id = unit_block.get("badgeId")
                if badge_id is not None:
                    item["unitBadgeId"] = badge_id
    return data


def build_recipe_data_payload(recipe: Recipe) -> Dict[str, Any]:
    """Return enriched RecipeData payload with nested food/unit structures."""
    payload = recipe.dict(by_alias=True)
    data = deepcopy(payload)
    # Ensure every ingredient and instruction has a stable id to support later mappings.
    _ensure_item_ids(data)
    sections = data.get("ingredients")
    if not isinstance(sections, list):
        return data
    for section in sections:
        items = section.get("ingredients")
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(list(items)):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            unit_text = item.get("unit")
            mealie_food_id = item.get("mealieFoodId")
            mealie_unit_id = item.get("mealieUnitId")
            food_badge = item.get("foodBadgeId")
            unit_badge = item.get("unitBadgeId")
            original_food = item.get("foodOriginalName") or name
            original_unit = item.get("unitOriginalName") or unit_text
            food_new_id = item.get("foodNewId")
            unit_new_id = item.get("unitNewId")
            food_block = {
                "name": name,
                "originalName": original_food,
            }
            if mealie_food_id is not None:
                food_block["mealieFoodId"] = mealie_food_id
            if food_badge is not None:
                food_block["badgeId"] = food_badge
            if food_new_id is not None:
                food_block["newId"] = food_new_id
            unit_block = {
                "name": unit_text,
                "originalName": original_unit,
            }
            if mealie_unit_id is not None:
                unit_block["mealieUnitId"] = mealie_unit_id
            if unit_badge is not None:
                unit_block["badgeId"] = unit_badge
            if unit_new_id is not None:
                unit_block["newId"] = unit_new_id
            new_item = {k: v for k, v in item.items() if k not in {
                "name",
                "unit",
                "mealieFoodId",
                "mealieUnitId",
                "foodBadgeId",
                "unitBadgeId",
                "foodOriginalName",
                "unitOriginalName",
                "foodNewId",
                "unitNewId",
            }}
            new_item["food"] = food_block
            new_item["unit"] = unit_block
            items[idx] = new_item
    return data


def _ensure_item_ids(data: Dict[str, Any]) -> None:
    """Add stable ids to ingredients/instructions when missing, so we can link them later."""
    ingredient_sections = data.get("ingredients") or []
    for s_idx, section in enumerate(ingredient_sections):
        items = section.get("ingredients") or []
        for i_idx, item in enumerate(items):
            if not item.get("id"):
                item["id"] = f"ing-{s_idx}-{i_idx}"
    instruction_sections = data.get("instructions") or []
    for s_idx, section in enumerate(instruction_sections):
        steps = section.get("steps") or []
        for i_idx, step in enumerate(steps):
            if not step.get("id"):
                step["id"] = f"step-{s_idx}-{i_idx}"
            if "ingredientIds" not in step or step.get("ingredientIds") is None:
                step["ingredientIds"] = []
            if "ingredientReferenceIds" not in step or step.get("ingredientReferenceIds") is None:
                step["ingredientReferenceIds"] = []


def auto_link_ingredients_to_instructions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Heuristic pre-fill: map instructions to ingredient ids if none set."""
    # Work on a copy to keep the caller's payload intact
    recipe = deepcopy(data)
    ingredient_sections = recipe.get("ingredients") or []
    instructions = recipe.get("instructions") or []

    # Build lookup of ingredient ids -> candidate names
    candidates: Dict[str, str] = {}
    for section in ingredient_sections:
        for item in section.get("ingredients") or []:
            ing_id = item.get("id")
            if not ing_id:
                continue
            names = [
                item.get("name") or "",
                (item.get("food") or {}).get("name") or "",
                (item.get("food") or {}).get("originalName") or "",
            ]
            # pick the longest non-empty name as matcher
            name = max([n for n in names if isinstance(n, str)], key=len, default="").strip()
            if name:
                candidates[ing_id] = name.lower()

    for section in instructions:
        for step in section.get("steps") or []:
            # Respect existing mappings
            existing = step.get("ingredientIds") or []
            if existing:
                continue
            text = (step.get("instruction") or "").lower()
            matched: list[str] = []
            for ing_id, needle in candidates.items():
                if needle and needle in text:
                    matched.append(ing_id)
            if matched:
                # de-duplicate while preserving order
                seen = set()
                deduped = []
                for mid in matched:
                    if mid in seen:
                        continue
                    seen.add(mid)
                    deduped.append(mid)
                step["ingredientIds"] = deduped
    logger.info(
        "Heuristic ingredient linking: %d ingredients, %d steps, %d steps matched",
        len(candidates),
        sum(len(sec.get("steps") or []) for sec in instructions),
        sum(1 for sec in instructions for st in sec.get("steps") or [] if st.get("ingredientIds")),
    )
    return recipe


@dataclass
class CachePaths:
    """Commonly used cache locations shared across runs."""

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def foods_cache(self) -> Path:
        return self.root / "MealieFoodsCache.json"

    @property
    def food_categories_cache(self) -> Path:
        return self.root / "MealieFoodCategoriesCache.json"

    @property
    def units_cache(self) -> Path:
        return self.root / "MealieUnitsCache.json"

    @property
    def recipe_categories_cache(self) -> Path:
        return self.root / "MealieRecipeCategoriesCache.json"

    @property
    def tags_cache(self) -> Path:
        return self.root / "MealieTagsCache.json"

    @property
    def tag_categories_cache(self) -> Path:
        return self.root / "MealieTagCategoriesCache.json"


@dataclass
class IngredientRef:
    """Reference to a single ingredient within the recipe structure."""

    section_index: int
    ingredient_index: int
    ingredient: Ingredient

    @property
    def key(self) -> str:
        return f"{self.section_index}:{self.ingredient_index}"


@dataclass
class PipelineContext:
    """Mutable processing state that is shared across modules."""

    source_pdf: Path
    output_dir: Path
    config: AppConfig
    cache_paths: CachePaths
    recipe_name: Optional[str] = None
    servings_hint: Optional[str] = None
    recipe_output_path: Optional[Path] = None
    recipe_data_path: Optional[Path] = None
    run_id: Optional[str] = None
    pipeline_recorder: Optional["PipelineRecorder"] = None
    log_file: Optional[Path] = None
    requires_user_review: bool = False
    food_review_path: Optional[Path] = None
    unit_review_path: Optional[Path] = None
    metadata_review_path: Optional[Path] = None
    food_decisions: Dict[str, Dict[str, object]] = field(default_factory=dict)
    unit_decisions: Dict[str, Dict[str, object]] = field(default_factory=dict)
    metadata_decision: Dict[str, object] = field(default_factory=dict)

    extraction: Optional[PdfExtractionResult] = None
    recipe: Optional[Recipe] = None
    food_matches: Dict[str, str] = field(default_factory=dict)
    missing_food_refs: List[IngredientRef] = field(default_factory=list)
    created_food_ids: Dict[str, str] = field(default_factory=dict)
    unit_matches: Dict[str, str] = field(default_factory=dict)
    missing_unit_refs: List[IngredientRef] = field(default_factory=list)
    created_unit_ids: Dict[str, str] = field(default_factory=dict)
    mealie_payload: Optional[Dict[str, object]] = None

    def ensure_extraction(self) -> PdfExtractionResult:
        if not self.extraction:
            raise RuntimeError("The PDF has not been read yet; please run the input module first")
        return self.extraction

    def ensure_recipe(self) -> Recipe:
        if self.recipe is None:
            if self.recipe_data_path and self.recipe_data_path.exists():
                raw = self.recipe_data_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                normalized = normalize_recipe_payload(data)
                self.recipe = Recipe.parse_obj(normalized)
                self._hydrate_recipe_assets()
            else:
                raise RuntimeError("RecipeData.json is not available yet")
        return self.recipe

    def save_recipe(self, recipe: Recipe, *, destination: Optional[Path] = None, overwrite: bool = True) -> None:
        self.recipe = recipe
        payload = build_recipe_data_payload(recipe)
        if destination is not None:
            self.recipe_data_path = destination
        if not self.recipe_data_path:
            raise RuntimeError("No save path for RecipeData.json has been configured")
        if overwrite:
            self.recipe_data_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def update_recipe_file(self) -> None:
        if self.recipe is None:
            return
        self.save_recipe(self.recipe)

    def iter_ingredients(self) -> Iterator[IngredientRef]:
        recipe = self.ensure_recipe()
        for section_index, section in enumerate(recipe.ingredients):
            for ingredient_index, ingredient in enumerate(section.ingredients):
                yield IngredientRef(
                    section_index=section_index,
                    ingredient_index=ingredient_index,
                    ingredient=ingredient,
                )

    def iter_ingredient_objects(self) -> Iterable[Ingredient]:  # pragma: no cover - helper for convenience
        for ref in self.iter_ingredients():
            yield ref.ingredient

    def mark_food_match(self, ref: IngredientRef, food_id: str) -> None:
        self.food_matches[ref.key] = food_id

    def mark_unit_match(self, ref: IngredientRef, unit_id: str) -> None:
        self.unit_matches[ref.key] = unit_id

    def cache_snapshot(self) -> Dict[str, str]:  # pragma: no cover - debug helper
        return {
            "foods_cache": str(self.cache_paths.foods_cache),
            "food_categories_cache": str(self.cache_paths.food_categories_cache),
            "units_cache": str(self.cache_paths.units_cache),
            "recipe_categories_cache": str(self.cache_paths.recipe_categories_cache),
            "tags_cache": str(self.cache_paths.tags_cache),
            "tag_categories_cache": str(self.cache_paths.tag_categories_cache),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _hydrate_recipe_assets(self) -> None:
        if not self.recipe or not self.recipe.assets:
            return
        base_dir = self.recipe_data_path.parent if self.recipe_data_path else self.output_dir
        for asset in self.recipe.assets:
            if getattr(asset, "data", None):
                continue

            def _resolve_path(path_str: str) -> Path:
                candidate = Path(path_str)
                if not candidate.is_absolute():
                    candidate = (base_dir / candidate).resolve()
                return candidate

            def _read_json(path: Path) -> Optional[Dict[str, Any]]:
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return None

            def _apply_payload(payload: Dict[str, Any], source_path: Optional[Path]) -> bool:
                data_url = payload.get("dataUrl") or payload.get("data")
                if not data_url:
                    return False
                asset.data = data_url
                if not asset.title:
                    asset.title = payload.get("title")
                if not asset.description:
                    asset.description = payload.get("description")
                if source_path and not asset.data_path:
                    try:
                        asset.data_path = str(source_path.relative_to(base_dir))
                    except ValueError:
                        asset.data_path = str(source_path)
                return True

            # 1) Try explicit data_path (JSON or binary)
            data_paths: List[Path] = []
            if getattr(asset, "data_path", None):
                data_paths.append(_resolve_path(str(asset.data_path)))

            # 2) Try known RecipeImage JSON snapshots
            for candidate in sorted(base_dir.glob("*RecipeImage*.json")):
                if candidate not in data_paths:
                    data_paths.append(candidate)

            applied = False
            for candidate in data_paths:
                if candidate.suffix.lower() == ".json":
                    payload = _read_json(candidate)
                    if not payload:
                        continue
                    file_name = payload.get("fileName")
                    if file_name and asset.file_name and file_name != asset.file_name:
                        continue
                    if _apply_payload(payload, candidate):
                        applied = True
                        break
                else:
                    try:
                        raw = candidate.read_bytes()
                    except OSError:
                        continue
                    mime_type, _ = mimetypes.guess_type(candidate.name)
                    mime_type = mime_type or "application/octet-stream"
                    data_url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
                    if _apply_payload({"dataUrl": data_url}, candidate):
                        applied = True
                        break

            if applied:
                continue

            # 3) Fallback to the actual image file (based on asset.file_name or recipe.image_path)
            image_candidates: List[Path] = []
            if asset.file_name:
                image_candidates.append(_resolve_path(asset.file_name))
            recipe_image_path = getattr(self.recipe, "image_path", None)
            if recipe_image_path:
                image_candidates.append(_resolve_path(recipe_image_path))

            seen: set[Path] = set()
            for candidate in image_candidates:
                candidate = candidate.resolve()
                if candidate in seen or not candidate.exists():
                    continue
                seen.add(candidate)
                mime_type, _ = mimetypes.guess_type(candidate.name)
                mime_type = mime_type or "application/octet-stream"
                try:
                    raw = candidate.read_bytes()
                except OSError:
                    continue
                data_url = f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
                if _apply_payload({"dataUrl": data_url}, candidate):
                    if not asset.file_name:
                        asset.file_name = candidate.name
                    break
