from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Dict, Any

PROMPT_FILE = Path("config/prompts.json")

FALLBACK_DEFAULTS: Dict[str, Dict[str, Dict[str, str]]] = {
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
        "instructions": {
            "free": "Zutaten (JSON): {ingredients}\nSchritte (JSON): {steps}\nAntwortformat: {\"links\":[{\"stepId\":\"...\",\"ingredientIds\":[\"...\"]}]}",
            "system": (
                "Du ordnest Zutaten den Zubereitungsschritten zu. "
                'Gib JSON mit Feld "links": [{stepId, ingredientIds[]}]. '
                "Nutze nur die gelieferten IDs; keine Freitext-Beschreibungen. "
                "Lasse ein Feld leer, wenn nichts passt."
            ),
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
        "instructions": {
            "free": "Ingredients (JSON): {ingredients}\nSteps (JSON): {steps}\nResponse format: {\"links\":[{\"stepId\":\"...\",\"ingredientIds\":[\"...\"]}]}",
            "system": (
                "You assign ingredients to preparation steps. "
                'Return JSON with field "links": [{stepId, ingredientIds[]}]. '
                "Use only provided IDs, no free text. Leave empty if nothing fits."
            ),
        },
    },
}


def _merge_prompts(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = deepcopy(base)
    if not isinstance(override, dict):
        return merged
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


def _load_prompt_file() -> tuple[Dict[str, Dict[str, Dict[str, str]]], Dict[str, Dict[str, Dict[str, str]]]]:
    if PROMPT_FILE.exists():
        try:
            data = json.loads(PROMPT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    else:
        data = {}

    if isinstance(data, dict) and "defaults" in data and "prompts" in data:
        defaults_section = data.get("defaults")
        prompts_section = data.get("prompts")
    else:
        defaults_section = None
        prompts_section = data if isinstance(data, dict) else None

    defaults = _merge_prompts(FALLBACK_DEFAULTS, defaults_section)
    prompts = _merge_prompts(defaults, prompts_section)
    return defaults, prompts


def load_prompts() -> Dict[str, Dict[str, Dict[str, str]]]:
    _, prompts = _load_prompt_file()
    return prompts


def save_prompts(data: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    defaults, _ = _load_prompt_file()
    PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"defaults": defaults, "prompts": data}
    PROMPT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_prompt_defaults() -> Dict[str, Dict[str, Dict[str, str]]]:
    defaults, _ = _load_prompt_file()
    return deepcopy(defaults)
