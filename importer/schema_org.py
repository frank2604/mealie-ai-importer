"""Produce schema.org/Recipe JSON from internal Recipe models."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Dict, Iterable, List, Optional

from .models import Ingredient, IngredientSection, InstructionSection, Recipe


@dataclass
class SchemaOrgRecipe:
    payload: Dict[str, Any]

    def to_json_string(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


def recipe_to_schemaorg(recipe: Recipe) -> SchemaOrgRecipe:
    data: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe.title,
        "description": recipe.description or "",
        "recipeIngredient": _ingredient_lines(recipe.ingredients),
        "recipeInstructions": _instruction_list(recipe.instructions),
    }

    if recipe.recipe_yield:
        data["recipeYield"] = recipe.recipe_yield
    elif recipe.recipe_servings:
        data["recipeYield"] = f"{recipe.recipe_servings:g} Portionen"
    if recipe.total_time:
        parsed_minutes = _parse_total_time_text(recipe.total_time)
        if parsed_minutes:
            data["totalTime"] = _format_iso_duration(parsed_minutes)
    if recipe.prep_time:
        parsed_prep = _parse_total_time_text(recipe.prep_time)
        if parsed_prep:
            data["prepTime"] = _format_iso_duration(parsed_prep)
    if recipe.perform_time:
        parsed_cook = _parse_total_time_text(recipe.perform_time)
        if parsed_cook:
            data["cookTime"] = _format_iso_duration(parsed_cook)

    if recipe.metadata.tags:
        data["keywords"] = ", ".join(recipe.metadata.tags)
    if recipe.metadata.cuisine:
        data["recipeCuisine"] = recipe.metadata.cuisine

    if recipe.notes:
        data["comment"] = [
            {
                "@type": "Comment",
                "text": recipe.notes,
            }
        ]

    if recipe.metadata.source:
        data["url"] = recipe.metadata.source

    if recipe.assets:
        images: List[Dict[str, Any]] = []
        for asset in recipe.assets:
            images.append(
                _clean_nulls(
                    {
                        "@type": "ImageObject",
                        "contentUrl": asset.data,
                        "name": asset.title or recipe.title,
                        "description": asset.description or recipe.description or recipe.title,
                    }
                )
            )
        data["image"] = images

    return SchemaOrgRecipe(data)


def _ingredient_lines(sections: Iterable[IngredientSection]) -> List[str]:
    lines: List[str] = []
    for section in sections:
        prefix = f"{section.name}: " if section.name else ""
        for ingredient in section.ingredients:
            lines.append(prefix + _ingredient_to_line(ingredient))
    return lines


def _ingredient_to_line(ingredient: Ingredient) -> str:
    amount = f"{ingredient.quantity:g}" if ingredient.quantity is not None else ""
    unit = ingredient.unit or ""
    parts = [part for part in [amount, unit, ingredient.name] if part]
    line = " ".join(parts)
    if ingredient.note:
        line += f" ({ingredient.note})"
    return line


def _instruction_list(sections: Iterable[InstructionSection]) -> List[Dict[str, Any]]:
    steps: List[Dict[str, Any]] = []
    for section in sections:
        for step in section.steps:
            entry: Dict[str, Any] = {
                "@type": "HowToStep",
                "text": step.instruction,
            }
            if section.name:
                entry["name"] = section.name
            steps.append(entry)
    return steps


def _format_iso_duration(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    parts = ["PT"]
    if hours:
        parts.append(f"{hours}H")
    if mins:
        parts.append(f"{mins}M")
    return "".join(parts)


_TIME_CHUNK_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(stunden?|std|hours?|hour|hrs?|hr|h|minuten?|mins?|min|m)?", re.I)


def _parse_total_time_text(raw_value: str) -> Optional[int]:
    """Best effort parser to convert free-form durations into minutes."""
    if not raw_value:
        return None
    text = raw_value.strip()
    if not text:
        return None
    total_minutes = 0.0
    matched = False
    for match in _TIME_CHUNK_RE.finditer(text):
        number_text = match.group(1)
        unit = (match.group(2) or "").lower()
        if not number_text:
            continue
        try:
            value = float(number_text.replace(",", "."))
        except ValueError:
            continue
        if not unit:
            continue
        matched = True
        if unit.startswith(("h", "st", "hour")):
            total_minutes += value * 60.0
        else:
            total_minutes += value
    if matched and total_minutes > 0:
        return int(round(total_minutes))
    digits = re.findall(r"\d+", text)
    if len(digits) == 1:
        try:
            return int(digits[0])
        except ValueError:
            return None
    return None


def _clean_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean_nulls(v) for k, v in value.items() if v not in (None, "")}
    if isinstance(value, list):
        return [_clean_nulls(v) for v in value if v not in (None, "")]
    return value
