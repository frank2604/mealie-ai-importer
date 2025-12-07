"""Convert internal Recipe models to Mealie JSON payloads."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from .models import Ingredient, IngredientSection, InstructionSection, OrganizerReference, Recipe, RecipeAsset
from .services.ingredients import FoodResource, IngredientService, UnitResource


@dataclass
class MealiePayload:
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return self.payload


def recipe_to_mealie(recipe: Recipe, ingredient_service: Optional[IngredientService] = None) -> MealiePayload:
    categories_payload = _map_organizer_refs(recipe.metadata.mealie_categories) or _map_name_list(
        recipe.metadata.categories
    )
    tags_payload = _map_organizer_refs(recipe.metadata.mealie_tags) or _map_name_list(recipe.metadata.tags)

    ingredients_payload, reference_map = _map_ingredients(recipe.ingredients, ingredient_service, recipe)

    payload: Dict[str, Any] = {
        "name": recipe.title,
        "description": recipe.description or "",
        "recipeServings": recipe.recipe_servings,
        "recipeYieldQuantity": recipe.recipe_yield_quantity,
        "recipeYield": recipe.recipe_yield,
        "recipeIngredient": ingredients_payload,
        "recipeInstructions": _map_instructions(recipe.instructions, reference_map),
        "recipeCategory": categories_payload,
        "tags": tags_payload,
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

    if recipe.total_time:
        payload["totalTime"] = recipe.total_time
    if recipe.prep_time:
        payload["prepTime"] = recipe.prep_time
    if recipe.perform_time:
        payload["performTime"] = recipe.perform_time
    if recipe.metadata.cuisine:
        payload.setdefault("tags", []).append(
            {"name": recipe.metadata.cuisine, "slug": _slugify(recipe.metadata.cuisine)}
        )
    if recipe.metadata.source:
        payload["orgURL"] = recipe.metadata.source

    payload = _clean_nulls(payload)
    return MealiePayload(payload)


def _map_ingredients(
    sections: Iterable[IngredientSection],
    service: Optional[IngredientService],
    recipe: Recipe,
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    entries: List[Dict[str, Any]] = []
    reference_map: Dict[str, str] = {}
    for section in sections:
        for ingr in section.ingredients:
            if getattr(ingr, "deleted", False):
                continue
            entry = _ingredient_to_entry(
                ingr,
                section_name=section.name,
                ingredient_service=service,
                recipe=recipe,
            )
            entries.append(entry)
            ref = entry.get("referenceId")
            if ref and (ingr.id or ref):
                if ingr.id:
                    reference_map[ingr.id] = ref
                else:
                    reference_map[ref] = ref
    return entries, reference_map


def _ingredient_to_entry(
    ingredient: Ingredient,
    *,
    section_name: Optional[str],
    ingredient_service: Optional[IngredientService],
    recipe: Recipe,
) -> Dict[str, Any]:
    if ingredient_service and ingredient.quantity is not None:
        unit_resource: Optional[UnitResource]
        if ingredient.mealie_unit_id:
            unit_resource = ingredient_service.get_unit_by_id(ingredient.mealie_unit_id)
        else:
            unit_resource = None
        if not unit_resource:
            unit_name = ingredient.unit or "Stück"
            unit_resource = ingredient_service.get_or_create_unit(
                name=unit_name,
                fraction=True,
            )

        category_hint = recipe.metadata.cuisine
        if recipe.metadata.categories:
            category_hint = recipe.metadata.categories[0]
        food_resource: Optional[FoodResource]
        if ingredient.mealie_food_id:
            food_resource = ingredient_service.get_food_by_id(ingredient.mealie_food_id)
        else:
            food_resource = None
        if not food_resource:
            food_resource = ingredient_service.get_or_create_food(
                name=ingredient.name,
                description="",
                category_hint=category_hint,
            )

        display_text = _build_display_string(ingredient)
        entry: Dict[str, Any] = {
            "quantity": ingredient.quantity,
            "note": ingredient.note,
            "unit": unit_resource.raw,
            "food": food_resource.raw,
        }
        entry["unitId"] = unit_resource.id
        entry["foodId"] = food_resource.id
        entry["display"] = display_text
        entry["originalText"] = display_text
        entry["display"] = _build_display_string(ingredient)
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
        entry["originalText"] = display

    if section_name and "title" not in entry:
        entry["title"] = section_name

    ref_id = ingredient.reference_id or ingredient.id or str(uuid4())
    entry["referenceId"] = ref_id
    return _clean_nulls(entry)


def _build_display_string(ingredient: Ingredient) -> str:
    amount = f"{ingredient.quantity:g}" if ingredient.quantity is not None else ""
    unit = ingredient.unit or ""
    parts = [part for part in [amount, unit, ingredient.name] if part]
    display = " ".join(parts)
    if ingredient.note:
        display += f" ({ingredient.note})"
    return display


def _map_instructions(sections: Iterable[InstructionSection], reference_map: Dict[str, str]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    for section in sections:
        for step in section.steps:
            # skip deleted ingredients in references
            valid_ids = [ing_id for ing_id in step.ingredient_ids if ing_id and ing_id in reference_map]
            ingredient_refs: List[Dict[str, str]] = []
            if step.ingredient_reference_ids:
                ingredient_refs = [{"referenceId": ref} for ref in step.ingredient_reference_ids if ref]
            elif step.ingredient_ids:
                for ing_id in valid_ids:
                    mapped = reference_map.get(ing_id, str(ing_id))
                    ingredient_refs.append({"referenceId": mapped})
            steps.append(
                _clean_nulls(
                    {
                        "id": str(uuid4()),
                        "title": section.name or "",
                        "summary": "",
                        "text": step.instruction,
                        "order": step.order,
                        "ingredientReferences": ingredient_refs,
                        "timerMinutes": step.timer_minutes,
                    }
                )
            )
    if not steps:
        return []
    return steps


def _map_name_list(names: Iterable[str]) -> List[Dict[str, Any]]:
    return [{"name": name, "slug": _slugify(name)} for name in names if name]


def _map_organizer_refs(refs: Iterable[OrganizerReference]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for ref in refs:
        if not ref.id or not ref.name:
            continue
        record: Dict[str, Any] = {
            "id": ref.id,
            "name": ref.name,
        }
        if ref.group_id:
            record["groupId"] = ref.group_id
        if ref.slug:
            record["slug"] = ref.slug
        items.append(record)
    return items


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
