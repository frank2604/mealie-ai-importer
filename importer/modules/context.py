"""Shared pipeline context and helper structures."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from ..config import AppConfig
from ..services.run_workspace import PipelineRecorder
from ..models import Ingredient, Recipe
from ..pdf_extractor import PdfExtractionResult


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
            if getattr(asset, "data", None) or not getattr(asset, "data_path", None):
                continue
            asset_path = Path(asset.data_path)
            if not asset_path.is_absolute():
                asset_path = (base_dir / asset_path).resolve()
            try:
                payload = json.loads(asset_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            asset.data = payload.get("dataUrl") or payload.get("data")
            if not asset.title:
                asset.title = payload.get("title")
            if not asset.description:
                asset.description = payload.get("description")
