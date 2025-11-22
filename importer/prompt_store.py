from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

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
        "foodForms": {
            "free": (
                "Bestimme Singular, Plural, Zählbarkeit und Aliasse und ordne jede Zutat einer vorhandenen Lebensmittelkategorie zu.\n"
                "Antworte ausschließlich mit JSON im beschriebenen Schema.\n\n"
                "Zutatenliste:\n{ingredient_lines}\n\n"
                "Verfügbare Kategorien (ID – Name):\n{category_lines}"
            ),
            "system": (
                "Du bist ein deutschsprachiger Zutaten-Normalizer für Mealie.\n"
                "Aufgabe: Für jede Zutat bestimmst du Singular, Plural, Zählbarkeit, nur strikte Aliasse sowie eine passende Lebensmittelkategorie aus der bereitgestellten Liste.\n\n"
                "Zählbar vs. unzählbar:\n"
                "Zählbar → unterschiedliche Formen (z. B. „1 Champignon“, „2 Champignons“).\n"
                "Unzählbar (Massenbegriffe wie Salz, Mehl, Sahne) → Form bleibt gleich.\n\n"
                "Strikte Aliasse nur für eindeutige Synonyme ohne Bedeutungswechsel; keine Unterarten, Marken oder Zubereitungszustände.\n"
                "Maximal 8 Aliasse, lowercase.\n\n"
                "Kategoriewahl: Verwende ausschließlich eine der vorgegebenen Kategorien, gib ID und Namen zurück, sonst null.\n"
                "Antworte nur mit JSON:\n"
                "{{\n"
                '  "ingredients": [\n'
                "    {{\n"
                '      "input": "...",\n'
                '      "nameSingular": "...",\n'
                '      "namePlural": "...",\n'
                '      "countable": true,\n'
                '      "aliasesStrict": ["...", "..."],\n'
                '      "categoryId": "...",\n'
                '      "categoryName": "..."\n'
                "    }}\n"
                "  ]\n"
                "}}\n"
                "Keine zusätzlichen Felder oder Erklärungen."
            ),
        },
        "unitForms": {
            "free": (
                "Erstelle für diese Einheiten passende Schreibweisen. Antworte ausschließlich mit JSON im beschriebenen Schema.\n\n"
                "{unit_lines}"
            ),
            "system": (
                "Du bereitest neue Mengeneinheiten für Mealie vor. Für jede Eingabe lieferst du Name, optionalen Plural sowie sinnvolle Abkürzungen.\n"
                "Regeln: Nur kochübliche Werte, Name ist Pflicht, pluralName nur wenn abweichend, Abkürzungen nur bei gebräuchlicher Kurzform, "
                'setze "useAbbreviation" nur dann auf true.\n'
                "Antwortschema:\n"
                "{{\n"
                '  "units": [\n'
                "    {{\n"
                '      "input": "...",\n'
                '      "name": "...",\n'
                '      "pluralName": "..." | null,\n'
                '      "abbreviation": "..." | null,\n'
                '      "pluralAbbreviation": "..." | null,\n'
                '      "useAbbreviation": true | false\n'
                "    }}\n"
                "  ]\n"
                "}}\n"
                "Keine Kommentare, keine zusätzlichen Felder."
            ),
        },
        "imageCrop": {
            "free": (
                "Rezepttitel: {title}\n"
                "Finde ausschließlich die Bildregion, auf der das fertig angerichtete Gericht inklusive Gefäß (Teller, Schale, Glas usw.) vollständig sichtbar ist. "
                "Vermeide Close-ups sowie Textspalten, Logos oder reine Dekoelemente. Gib ein JSON-Objekt mit dem Feld \"crop\" zurück:\n"
                "{{\n"
                '  "crop": {{"x": ..., "y": ..., "width": ..., "height": ...}}\n'
                "}}\n"
                "Alle Werte sind relative Koordinaten (0.0–1.0). Falls kein sinnvolles Gericht erkennbar ist, setze \"crop\" auf null."
            ),
            "system": "Du bist ein präziser Assistent für Bildausschnitte. Antworte ausschließlich mit JSON und halte dich strikt an die Koordinatenvorgabe.",
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
        "foodForms": {
            "free": (
                "Determine singular, plural, countability and strict aliases, then map every ingredient to an existing food category.\n"
                "Respond with JSON only.\n\n"
                "Ingredient list:\n{ingredient_lines}\n\n"
                "Available categories (ID – name):\n{category_lines}"
            ),
            "system": (
                "You normalize ingredients for Mealie. For each entry, provide singular, plural, whether it is countable, "
                "strict aliases and an appropriate category from the provided list.\n"
                "Countable vs. uncountable: countable → distinct plural form; uncountable (salt, flour, cream) keeps the same word.\n"
                "Strict aliases are exact synonyms only; no subtypes, preparations or brands. Lowercase, max 8 entries.\n"
                "Use only the supplied categories and return both id and name (or null if none fits).\n"
                "JSON schema:\n"
                "{{\n"
                '  "ingredients": [\n'
                "    {{\n"
                '      "input": "...",\n'
                '      "nameSingular": "...",\n'
                '      "namePlural": "...",\n'
                '      "countable": true,\n'
                '      "aliasesStrict": ["...", "..."],\n'
                '      "categoryId": "...",\n'
                '      "categoryName": "..."\n'
                "    }}\n"
                "  ]\n"
                "}}\n"
                "No additional text."
            ),
        },
        "unitForms": {
            "free": (
                "Create suitable spellings for these units. Respond strictly as JSON in the described schema.\n\n"
                "{unit_lines}"
            ),
            "system": (
                "You prepare cooking units for Mealie. For each unit provide name, optional plural and well-known abbreviations.\n"
                "Rules: keep names kitchen-appropriate, plural only when different, abbreviations only if commonly used, "
                'set "useAbbreviation" to true only then.\n'
                "JSON schema:\n"
                "{{\n"
                '  "units": [\n'
                "    {{\n"
                '      "input": "...",\n'
                '      "name": "...",\n'
                '      "pluralName": "..." | null,\n'
                '      "abbreviation": "..." | null,\n'
                '      "pluralAbbreviation": "..." | null,\n'
                '      "useAbbreviation": true | false\n'
                "    }}\n"
                "  ]\n"
                "}}\n"
                "No extra commentary."
            ),
        },
        "imageCrop": {
            "free": (
                "Recipe title: {title}\n"
                "Find only the region that shows the fully plated dish including its vessel (plate, bowl, glass, etc.). "
                "Avoid close-ups, text columns, logos or pure decoration. Return JSON with a \"crop\" field:\n"
                "{{\n"
                '  "crop": {{"x": ..., "y": ..., "width": ..., "height": ...}}\n'
                "}}\n"
                "Values are relative (0.0–1.0). If no reasonable dish is visible, set \"crop\" to null."
            ),
            "system": "You are a precise cropping assistant. Respond with JSON only and follow the coordinate format exactly.",
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


def resolve_prompt(module: str, locale: Optional[str] = None) -> Dict[str, str]:
    """Return the prompt texts for *module* using *locale* with fallbacks."""
    defaults, prompts = _load_prompt_file()

    def _lookup(source: Dict[str, Dict[str, Dict[str, str]]], loc: Optional[str]) -> Optional[Dict[str, str]]:
        if not loc:
            return None
        return source.get(loc, {}).get(module)

    locale_key = (locale or "de") or "de"
    base_locale = locale_key.split("-")[0]

    candidates = []
    for key in (locale, locale_key, base_locale, "de", "en"):
        if key and key not in candidates:
            candidates.append(key)
    for key in prompts.keys():
        if key not in candidates:
            candidates.append(key)

    # First try user prompts, then defaults
    for loc in candidates:
        found = _lookup(prompts, loc)
        if found:
            return {"free": found.get("free", ""), "system": found.get("system", "")}
    for loc in candidates:
        found = _lookup(defaults, loc)
        if found:
            return {"free": found.get("free", ""), "system": found.get("system", "")}
    return {"free": "", "system": ""}
