"""Shared pipeline context and helper structures."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from ..config import AppConfig
from ..models import Ingredient, Recipe
from ..pdf_extractor import PdfExtractionResult


@dataclass
class CachePaths:
    """Commonly used cache locations for a processing run."""

    root: Path
    recipe_key: str

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.recipe_dir.mkdir(parents=True, exist_ok=True)

    @property
    def recipe_dir(self) -> Path:
        return self.root / self.recipe_key

    @property
    def recipe_raw(self) -> Path:
        return self.recipe_dir / "RecipeRawData.json"

    @property
    def foods_cache(self) -> Path:
        return self.root / "MealieFoodsCache.json"

    @property
    def food_categories_cache(self) -> Path:
        return self.root / "MealieFoodCategoriesCache.json"

    @property
    def units_cache(self) -> Path:
        return self.root / "MealieUnitsCache.json"


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
            raise RuntimeError("PDF wurde noch nicht eingelesen – Input-Modul zuerst ausführen")
        return self.extraction

    def ensure_recipe(self) -> Recipe:
        if self.recipe is None:
            if self.cache_paths.recipe_raw.exists():
                raw = self.cache_paths.recipe_raw.read_text(encoding="utf-8")
                data = json.loads(raw)
                self.recipe = Recipe.parse_obj(data)
            else:
                raise RuntimeError("Es liegt noch kein RecipeRawData.json vor")
        return self.recipe

    def save_recipe(self, recipe: Recipe) -> None:
        self.recipe = recipe
        payload = recipe.dict(by_alias=True)
        self.cache_paths.recipe_raw.write_text(
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
            "recipe_raw": str(self.cache_paths.recipe_raw),
            "foods_cache": str(self.cache_paths.foods_cache),
            "food_categories_cache": str(self.cache_paths.food_categories_cache),
            "units_cache": str(self.cache_paths.units_cache),
            "timestamp": datetime.utcnow().isoformat(),
        }

