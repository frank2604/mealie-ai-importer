"""Shared pipeline context and helper structures."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from ..config import AppConfig
from ..services.run_workspace import PipelineRecorder
from ..models import Ingredient, Recipe
from ..pdf_extractor import PdfExtractionResult


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
                self.recipe = Recipe.parse_obj(data)
                self._hydrate_recipe_assets()
            else:
                raise RuntimeError("RecipeData.json is not available yet")
        return self.recipe

    def save_recipe(self, recipe: Recipe, *, destination: Optional[Path] = None, overwrite: bool = True) -> None:
        self.recipe = recipe
        payload = recipe.dict(by_alias=True)
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
