"""Convert internal Recipe models to Mealie JSON payloads."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import Ingredient, IngredientSection, InstructionSection, Recipe, RecipeAsset
from .services.ingredients import IngredientService


@dataclass
class MealiePayload:
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


def recipe_to_mealie(recipe: Recipe, ingredient_service: Optional[IngredientService] = None) -> MealiePayload:
    _REFERENCE_COUNTER.clear()
    payload: Dict[str, Any] = {
        "name": recipe.title,
        "description": recipe.description or "",
        "recipeServings": recipe.portions,
        "recipeIngredient": _map_ingredients(recipe.ingredients, ingredient_service, recipe),
        "recipeInstructions": _map_instructions(recipe.instructions),
        "recipeCategory": _map_name_list(recipe.metadata.categories),
        "tags": _map_name_list(recipe.metadata.tags),
        "tools": [],
        "settings": {
            "public": False,
            "showNutrition": False,
            "showAssets": True,
            "landscapeView": False,
            "disableComments": False,
            "locked": False,
        },
        "assets": _map_assets(recipe.assets, recipe.title),
        "notes": _map_notes(recipe.notes),
    }

    if recipe.total_time_minutes:
        payload["totalTime"] = _format_minutes(recipe.total_time_minutes)
    if recipe.metadata.cuisine:
        payload.setdefault("tags", []).append({"name": recipe.metadata.cuisine})
    if recipe.metadata.source:
        payload["orgURL"] = recipe.metadata.source

    payload = _clean_nulls(payload)
    return MealiePayload(payload)


def _map_ingredients(
    sections: Iterable[IngredientSection],
    service: Optional[IngredientService],
    recipe: Recipe,
) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for section in sections:
        for ingr in section.ingredients:
            entries.append(
                _ingredient_to_entry(
                    ingr,
                    section_name=section.name,
                    ingredient_service=service,
                    recipe=recipe,
                )
            )
    return entries


def _ingredient_to_entry(
    ingredient: Ingredient,
    *,
    section_name: Optional[str],
    ingredient_service: Optional[IngredientService],
    recipe: Recipe,
) -> Dict[str, Any]:
    if ingredient_service and ingredient.quantity is not None:
        unit_resource = ingredient_service.get_or_create_unit(
            name=ingredient.unit or "Stück",
            plural_name=ingredient.unit or "Stück",
            abbreviation=ingredient.unit or "",
            fraction=True,
        )

        category_hint = recipe.metadata.cuisine
        if recipe.metadata.categories:
            category_hint = recipe.metadata.categories[0]
        food_resource = ingredient_service.get_or_create_food(
            name=ingredient.name,
            description=ingredient.note or "",
            category_hint=category_hint,
        )

        entry: Dict[str, Any] = {
            "quantity": ingredient.quantity,
            "note": ingredient.note,
            "unit": unit_resource.raw,
            "food": food_resource.raw,
        }
        entry["unitId"] = unit_resource.id
        entry["foodId"] = food_resource.id
        entry["display"] = _build_display_string(ingredient)
        entry["referenceId"] = _reference_id(ingredient)
    else:
        amount = f"{ingredient.quantity:g}" if ingredient.quantity is not None else ""
        unit = ingredient.unit or ""
        parts = [part for part in [amount, unit, ingredient.name] if part]
        display = " ".join(parts)
        if ingredient.note:
            display += f" ({ingredient.note})"
        entry = {
            "note": display,
            "display": display,
        }

    if section_name and "title" not in entry:
        entry["title"] = section_name

    return _clean_nulls(entry)


_REFERENCE_COUNTER = {}


def _reference_id(ingredient: Ingredient) -> str:
    key = _normalize_ref(ingredient.name)
    count = _REFERENCE_COUNTER.get(key, 0) + 1
    _REFERENCE_COUNTER[key] = count
    return f"{key}-{count}"


def _normalize_ref(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _build_display_string(ingredient: Ingredient) -> str:
    amount = f"{ingredient.quantity:g}" if ingredient.quantity is not None else ""
    unit = ingredient.unit or ""
    parts = [part for part in [amount, unit, ingredient.name] if part]
    display = " ".join(parts)
    if ingredient.note:
        display += f" ({ingredient.note})"
    return display


def _map_instructions(sections: Iterable[InstructionSection]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    for section in sections:
        for step in section.steps:
            steps.append(
                _clean_nulls(
                    {
                        "title": section.name or "",
                        "text": step.instruction,
                        "summary": "",
                    }
                )
            )
    if not steps:
        return []
    # Mealie expects at least empty title field
    return steps


def _map_name_list(names: Iterable[str]) -> List[Dict[str, Any]]:
    return [{"name": name, "slug": _slugify(name)} for name in names if name]


def _map_assets(assets: Iterable[RecipeAsset], title: str) -> List[Dict[str, Any]]:
    mapped: List[Dict[str, Any]] = []
    for asset in assets:
        if not asset.data:
            continue
        mapped.append(
            _clean_nulls(
                {
                    "fileName": asset.file_name,
                    "data": asset.data,
                    "title": asset.title or title,
                    "description": asset.description or "",
                }
            )
        )
    return mapped


def _map_notes(notes: Optional[str]) -> List[Dict[str, Any]]:
    if not notes:
        return []
    return [
        {
            "title": "Hinweis",
            "text": notes,
        }
    ]


def _format_minutes(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} Minuten"
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} Stunden")
    if mins:
        parts.append(f"{mins} Minuten")
    return " ".join(parts)


def _clean_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean_nulls(v) for k, v in value.items() if v not in (None, "")}
    if isinstance(value, list):
        return [_clean_nulls(v) for v in value if v not in (None, "")]
    return value


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")
