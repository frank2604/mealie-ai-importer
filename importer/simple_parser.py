"""Simple heuristic parser for recipe text.

This is an interim solution before the LLM-based parser is wired up. It tries to
split the extracted PDF text into ingredients and instructions using common
headings such as "Zutaten" and "Zubereitung".
"""
from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path
from typing import Iterable, List

from .models import (
    Ingredient,
    IngredientSection,
    InstructionSection,
    InstructionStep,
    Recipe,
    RecipeMetadata,
)


HEADING_INGREDIENTS = {"zutaten", "zutaten:"}
HEADING_INSTRUCTIONS = {"zubereitung", "zubereitung:"}
IGNORE_PREFIXES = (
    "dieser artikel",
    "https://",
    "stand:",
    "seite ",
    "impressum",
)
METADATA_LINES = {
    "nährwerte pro portion",
    "geeignet u. a. bei:",
}

_INGREDIENT_PATTERN = re.compile(r"^(?P<amount>[\d\,\.\/ ]+)?\s*(?P<unit>[A-Za-zäöüÄÖÜß]+)?\s*(?P<name>.+)$")


def parse_recipe(text: str, source: Path) -> Recipe:
    """Return a Recipe instance built from plain PDF text."""
    lines = _prepare_lines(text)

    if not lines:
        raise ValueError("Keine verwertbaren Textzeilen im PDF gefunden")

    title = _detect_title(lines, source)

    ingredient_lines, instruction_lines = _split_sections(lines)

    if not instruction_lines:
        instruction_lines = _fallback_instructions(lines, ingredient_lines)

    ingredients = _parse_ingredients(ingredient_lines)
    instructions = _parse_instructions(instruction_lines)

    metadata = RecipeMetadata(source=str(source))

    return Recipe(
        title=title,
        ingredients=[IngredientSection(name=None, ingredients=ingredients)] if ingredients else [],
        instructions=[InstructionSection(name=None, steps=instructions)] if instructions else [],
        metadata=metadata,
    )


def _prepare_lines(text: str) -> List[str]:
    cleaned: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if any(lower.startswith(prefix) for prefix in IGNORE_PREFIXES):
            continue
        cleaned.append(stripped)
    return cleaned


def _detect_title(lines: List[str], source: Path) -> str:
    for line in lines:
        normalized = line.lower()
        if normalized in HEADING_INGREDIENTS or normalized in HEADING_INSTRUCTIONS:
            continue
        if normalized in METADATA_LINES:
            continue
        if any(normalized.startswith(prefix) for prefix in IGNORE_PREFIXES):
            continue
        if normalized.endswith(".html"):
            continue
        if "person" in normalized and "(" in normalized:
            continue
        if _looks_like_ingredient(line):
            continue
        if len(line.split()) < 2:
            continue
        if any(char.isdigit() for char in line):
            continue
        if any(punct in line for punct in (",", ":", "(", ")", ".")):
            continue
        return line

    fallback = source.stem
    if " _ " in fallback:
        fallback = fallback.split(" _ ", 1)[0]
    fallback = re.sub(r"[_-]+", " ", fallback).strip()
    return fallback or "Unbenanntes Rezept"


def _split_sections(lines: Iterable[str]) -> tuple[List[str], List[str]]:
    ingredients: List[str] = []
    instructions: List[str] = []
    current = None

    for line in lines:
        normalized = line.lower()
        if normalized in HEADING_INGREDIENTS:
            current = "ingredients"
            continue
        if normalized in HEADING_INSTRUCTIONS:
            current = "instructions"
            continue
        if normalized in METADATA_LINES:
            current = "metadata"
            continue

        if current == "ingredients":
            if _looks_like_ingredient(line):
                ingredients.append(line)
                continue
            current = "instructions"

        if current == "instructions":
            instructions.append(line)

    return ingredients, instructions


def _fallback_instructions(all_lines: List[str], ingredient_lines: List[str]) -> List[str]:
    instructions: List[str] = []
    skip = set(ingredient_lines)
    for line in all_lines:
        lower = line.lower()
        if line in skip or lower in HEADING_INGREDIENTS:
            continue
        if _looks_like_ingredient(line):
            continue
        if lower in METADATA_LINES:
            break
        instructions.append(line)
    return instructions


def _looks_like_ingredient(line: str) -> bool:
    match = _INGREDIENT_PATTERN.match(line)
    if not match:
        return False
    amount = (match.group("amount") or "").strip()
    name = (match.group("name") or "").strip()
    if amount:
        return True
    tokens = name.split()
    return bool(tokens) and tokens[0][0].isdigit()


def _parse_ingredients(lines: Iterable[str]) -> List[Ingredient]:
    parsed: List[Ingredient] = []

    for line in lines:
        match = _INGREDIENT_PATTERN.match(line)
        if not match:
            parsed.append(Ingredient(name=line))
            continue

        amount = (match.group("amount") or "").strip()
        unit = (match.group("unit") or "").strip() or None
        name = match.group("name").strip()

        quantity = None
        if amount:
            normalized = amount.replace(",", ".")
            try:
                quantity = float(Fraction(normalized))
            except (ValueError, ZeroDivisionError):  # pragma: no cover - defensive
                try:
                    quantity = float(normalized)
                except ValueError:
                    quantity = None

        parsed.append(Ingredient(name=name, quantity=quantity, unit=unit))

    return parsed


def _parse_instructions(lines: Iterable[str]) -> List[InstructionStep]:
    steps: List[InstructionStep] = []

    for index, line in enumerate(lines, start=1):
        steps.append(InstructionStep(order=index, instruction=line))

    return steps
