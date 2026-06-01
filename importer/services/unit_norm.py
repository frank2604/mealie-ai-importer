"""Curated German unit normalization.

Units are a small, closed vocabulary where the matching problem is *spelling
variation* (g / gr / Gramm), NOT semantic similarity. Embeddings are explicitly
the wrong tool here: "EL" (Esslöffel) and "TL" (Teelöffel) are semantically very
close yet must NEVER be treated as the same unit. So we use a hand-curated
synonym table with strict, separate canonical keys.

`canonical_unit(raw)` returns the canonical token for a recipe unit string, or
None if it is not a known standard unit (in which case the caller falls back to
exact matching against Mealie's own units and, ultimately, the LLM).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

__all__ = ["canonical_unit", "variants_for", "CANONICAL_UNITS"]

# canonical -> list of accepted variants (all compared case-insensitively, with
# trailing dots stripped). The canonical spelling itself is included implicitly.
# IMPORTANT: EL and TL are deliberately kept as separate keys and never share a
# variant — they must not cross-map.
CANONICAL_UNITS: Dict[str, List[str]] = {
    "g": ["g", "gr", "gramm", "gramms"],
    "kg": ["kg", "kilo", "kilos", "kilogramm"],
    "mg": ["mg", "milligramm"],
    "ml": ["ml", "milliliter"],
    "l": ["l", "liter", "ltr"],
    "EL": ["el", "essl", "esslöffel", "eßlöffel", "esslöffeln", "tablespoon", "tbsp"],
    "TL": ["tl", "teel", "teelöffel", "teelöffeln", "teaspoon", "tsp"],
    "Prise": ["prise", "prisen", "pinch"],
    "Stück": ["stück", "stücke", "stücken", "stk", "st", "stueck", "piece", "pieces"],
    "Bund": ["bund", "bünde", "bunde"],
    "Zehe": ["zehe", "zehen"],
    "Dose": ["dose", "dosen", "can", "cans"],
    "Glas": ["glas", "gläser"],
    "Packung": ["packung", "packungen", "pkg", "pck", "pck.", "päckchen", "paeckchen", "pack"],
    "Becher": ["becher"],
    "Tasse": ["tasse", "tassen", "cup", "cups"],
    "Msp": ["msp", "messerspitze", "messerspitzen"],
    "Scheibe": ["scheibe", "scheiben", "slice", "slices"],
    "Blatt": ["blatt", "blätter", "blaetter"],
    "Tropfen": ["tropfen", "drop", "drops"],
}

# Build reverse lookup: variant -> canonical. We also map each canonical's own
# lowercased form to itself. A startup assertion guards against a variant being
# accidentally shared between two canonicals (e.g. someone adding "el" to TL).
_VARIANT_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _variants in CANONICAL_UNITS.items():
    for _variant in [_canonical.lower(), *(_variants)]:
        _key = _variant.lower()
        if _key in _VARIANT_TO_CANONICAL and _VARIANT_TO_CANONICAL[_key] != _canonical:
            raise AssertionError(
                f"Unit variant '{_key}' maps to both "
                f"'{_VARIANT_TO_CANONICAL[_key]}' and '{_canonical}'"
            )
        _VARIANT_TO_CANONICAL[_key] = _canonical

_CLEAN_RE = re.compile(r"\s+")


def _clean(raw: str) -> str:
    text = (raw or "").strip().lower()
    text = text.rstrip(".")
    return _CLEAN_RE.sub(" ", text)


def canonical_unit(raw: str) -> Optional[str]:
    """Return the canonical unit token for *raw*, or None if unknown."""
    cleaned = _clean(raw)
    if not cleaned:
        return None
    return _VARIANT_TO_CANONICAL.get(cleaned)


def variants_for(canonical: str) -> List[str]:
    """Return all accepted variants (including the canonical) for a canonical key."""
    if canonical not in CANONICAL_UNITS:
        return []
    seen: List[str] = []
    for value in [canonical, *CANONICAL_UNITS[canonical]]:
        if value not in seen:
            seen.append(value)
    return seen
