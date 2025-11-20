from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any

PROMPT_FILE = Path("config/prompts.json")

DEFAULT_PROMPTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "de": {
        "analysis": {
            "free": "Du bist ein Rezept-Analyse-Experte und beschreibst den Ablauf …",
            "system": "Antworte nur als JSON, nutze Platzhalter wie {{recipeText}} unverändert.",
        },
        "ingredients": {
            "free": "Ordne Zutaten passenden Mealie-Lebensmitteln zu …",
            "system": "Gib Zuordnungen mit IDs zurück, behalte Platzhalter bei.",
        },
        "units": {
            "free": "Mappe Einheiten auf standardisierte Mealie-Einheiten …",
            "system": "Liefere IDs/Neu-Einträge für Einheiten im JSON-Format.",
        },
        "metadata": {
            "free": "Schlage Kategorien und Tags für dieses Rezept vor …",
            "system": "Nutze nur die bereitgestellten IDs, antworte exakt im JSON-Schema.",
        },
    },
    "en": {
        "analysis": {
            "free": "You are an AI chef that analyses the uploaded recipe…",
            "system": "Respond only in JSON, keep placeholders intact, use {{recipeText}} etc.",
        },
        "ingredients": {
            "free": "Match ingredients to Mealie foods …",
            "system": "Return mappings with IDs, handle new foods, keep placeholders.",
        },
        "units": {
            "free": "Map units to Mealie standard units …",
            "system": "Return mappings with unit IDs, keep placeholders.",
        },
        "metadata": {
            "free": "Suggest categories/tags for this recipe …",
            "system": "Use the provided ID lists, return JSON {categoryId, tags:[…]}.",
        },
    },
}


def _merge_prompts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for locale, modules in override.items():
        if not isinstance(modules, dict):
            continue
        locale_entry = merged.setdefault(locale, {})
        for module, values in modules.items():
            if not isinstance(values, dict):
                continue
            module_entry = locale_entry.setdefault(module, {})
            for key in ("free", "system"):
                if key in values and isinstance(values[key], str):
                    module_entry[key] = values[key]
    return merged


def load_prompts() -> Dict[str, Dict[str, Dict[str, str]]]:
    if PROMPT_FILE.exists():
        try:
            data = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}
    merged = _merge_prompts(DEFAULT_PROMPTS, data)
    return merged


def save_prompts(data: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_prompt_defaults() -> Dict[str, Dict[str, Dict[str, str]]]:
    return deepcopy(DEFAULT_PROMPTS)
