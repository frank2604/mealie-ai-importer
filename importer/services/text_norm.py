"""Shared German text normalization helpers for ingredient/food matching.

These helpers are intentionally pure (no I/O, no LLM) so they are cheap, fully
deterministic, and easy to unit test. They are used by the food matcher, the
embedding index, and the ingredient service to keep the *normalized exact match*
behaviour consistent everywhere (previously each module rolled its own lowercase
logic, which drifted apart).
"""
from __future__ import annotations

import re
from typing import Iterable, List

__all__ = ["normalize_de", "fold_umlauts", "strip_qualifiers", "tokens"]

# Descriptive qualifiers that do not change the *identity* of a food and should
# be ignored when matching against existing Mealie foods. Kept deliberately
# small and conservative: we only strip words that are clearly preparation/state
# descriptors, never words that could distinguish two real foods.
_QUALIFIERS = {
    "frisch", "frische", "frischer", "frisches", "frischen", "frischem",
    "gehackt", "gehackte", "gehackter", "gehacktes", "gehackten",
    "gerieben", "geriebene", "geriebener", "geriebenes", "geriebenen",
    "getrocknet", "getrocknete", "getrockneter", "getrocknetes", "getrockneten",
    "gemahlen", "gemahlene", "gemahlener", "gemahlenes", "gemahlenen",
    "gewürfelt", "gewürfelte", "gewürfelter", "gewürfeltes", "gewürfelten",
    "fein", "feine", "feiner", "feines", "feinen",
    "grob", "grobe", "grober", "grobes", "groben",
    "klein", "kleine", "kleiner", "kleines", "kleinen",
    "geschält", "geschälte", "geschälter", "geschältes", "geschälten",
}

_WHITESPACE_RE = re.compile(r"\s+")
# Strip leading "ca.", "etwas", "evtl." and similar measurement noise that
# sometimes leaks into the food name field.
_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")

_UMLAUT_MAP = {
    ord("ä"): "ae",
    ord("ö"): "oe",
    ord("ü"): "ue",
    ord("ß"): "ss",
    ord("Ä"): "ae",
    ord("Ö"): "oe",
    ord("Ü"): "ue",
}


def fold_umlauts(value: str) -> str:
    """Replace German umlauts with their ASCII digraphs (ä -> ae)."""
    return value.translate(_UMLAUT_MAP)


def tokens(value: str) -> List[str]:
    """Split *value* into lowercase word tokens (umlaut-preserving)."""
    cleaned = _PARENTHETICAL_RE.sub(" ", value or "")
    return [t for t in _WHITESPACE_RE.split(cleaned.strip().lower()) if t]


def strip_qualifiers(word_tokens: Iterable[str]) -> List[str]:
    """Drop descriptive qualifier tokens (frisch, gehackt, ...).

    If *every* token is a qualifier we keep the original tokens, because in that
    odd case the qualifier presumably *is* the name.
    """
    kept = [t for t in word_tokens if t not in _QUALIFIERS]
    return kept or list(word_tokens)


def normalize_de(value: str, *, fold: bool = False) -> str:
    """Normalize a German food/ingredient name for matching.

    Steps: drop parentheticals, lowercase, split into tokens, remove descriptive
    qualifiers, collapse whitespace. Umlaut folding is OFF by default because
    "ä" vs "a" rarely separates two real foods while over-folding risks merging
    distinct names; enable via *fold* when a looser key is wanted.
    """
    word_tokens = strip_qualifiers(tokens(value))
    result = " ".join(word_tokens)
    if fold:
        result = fold_umlauts(result)
    return result
