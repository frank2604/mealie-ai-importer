from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

PROMPT_FILE = Path("config/prompts.json")

LLM_CONFIG_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "analysis": {"model": "gpt-5-mini", "temperature": 0.3, "top_p": 1.0, "max_output_tokens": 2500},
    "ingredients": {"model": "gpt-5-nano", "temperature": 0.0, "top_p": 1.0, "max_output_tokens": 200},
    "units": {"model": "gpt-5-nano", "temperature": 0.0, "top_p": 1.0, "max_output_tokens": 150},
    "metadata": {"model": "gpt-5-mini", "temperature": 0.3, "top_p": 1.0, "max_output_tokens": 400},
    "instructions": {"model": "gpt-5-mini", "temperature": 0.0, "top_p": 1.0, "max_output_tokens": 600},
    "foodForms": {"model": "gpt-5-mini", "temperature": 0.5, "top_p": 1.0, "max_output_tokens": 600},
    "unitForms": {"model": "gpt-5-mini", "temperature": 0.3, "top_p": 1.0, "max_output_tokens": 400},
    "imageCrop": {"model": "gpt-4o-mini", "temperature": 0.0, "top_p": 1.0, "max_output_tokens": 150},
}

FALLBACK_DEFAULTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "de": {
        "analysis": {
            "user1": "Du bist ein Rezept-Analyse-Experte und beschreibst den Ablauf …",
            "user2": "",
            "system": "Antworte nur als JSON, nutze Platzhalter wie {{recipeText}} unverändert.",
        },
        "ingredients": {
            "user1": "Ordne Zutaten passenden Mealie-Lebensmitteln zu …",
            "user2": "",
            "system": "Gib Zuordnungen mit IDs zurück, behalte Platzhalter bei.",
        },
        "units": {
            "user1": "Mappe Einheiten auf standardisierte Mealie-Einheiten …",
            "user2": "",
            "system": "Liefere IDs/Neu-Einträge für Einheiten im JSON-Format.",
        },
        "metadata": {
            "user1": "Schlage Kategorien und Tags für dieses Rezept vor …",
            "user2": "",
            "system": "Nutze nur die bereitgestellten IDs, antworte exakt im JSON-Schema.",
        },
        "instructions": {
            "user1": "Zutaten (JSON): {ingredients}\nSchritte (JSON): {steps}\nAntwortformat: {\"links\":[{\"stepId\":\"...\",\"ingredientIds\":[\"...\"]}]}",
            "user2": "",
            "system": (
                "Du ordnest Zutaten den Zubereitungsschritten zu. "
                'Gib JSON mit Feld "links": [{stepId, ingredientIds[]}]. '
                "Nutze nur die gelieferten IDs; keine Freitext-Beschreibungen. "
                "Lasse ein Feld leer, wenn nichts passt."
            ),
        },
        "foodForms": {
            "user1": (
                "Bestimme Singular, Plural, Zählbarkeit und Aliasse und ordne jede Zutat einer vorhandenen Lebensmittelkategorie zu.\n"
                "Antworte ausschließlich mit JSON im beschriebenen Schema.\n\n"
                "Zutatenliste:\n{ingredient_lines}\n\n"
                "Verfügbare Kategorien (ID – Name):\n{category_lines}"
            ),
            "user2": "",
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
            "user1": (
                "Erstelle für diese Einheiten passende Schreibweisen. Antworte ausschließlich mit JSON im beschriebenen Schema.\n\n"
                "{unit_lines}"
            ),
            "user2": "",
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
            "user1": (
                "Rezepttitel: {title}\n"
                "Finde ausschließlich die Bildregion, auf der das fertig angerichtete Gericht inklusive Gefäß (Teller, Schale, Glas usw.) vollständig sichtbar ist. "
                "Vermeide Close-ups sowie Textspalten, Logos oder reine Dekoelemente. Gib ein JSON-Objekt mit dem Feld \"crop\" zurück:\n"
                "{{\n"
                '  "crop": {{"x": ..., "y": ..., "width": ..., "height": ...}}\n'
                "}}\n"
                "Alle Werte sind relative Koordinaten (0.0–1.0). Falls kein sinnvolles Gericht erkennbar ist, setze \"crop\" auf null."
            ),
            "user2": "",
            "system": "Du bist ein präziser Assistent für Bildausschnitte. Antworte ausschließlich mit JSON und halte dich strikt an die Koordinatenvorgabe.",
        },
    },
    "en": {
        "analysis": {
            "user1": "You are an AI chef that analyses the uploaded recipe…",
            "user2": "",
            "system": "Respond only in JSON, keep placeholders intact, use {{recipeText}} etc.",
        },
        "ingredients": {
            "user1": "Match ingredients to Mealie foods …",
            "user2": "",
            "system": "Return mappings with IDs, handle new foods, keep placeholders.",
        },
        "units": {
            "user1": "Map units to Mealie standard units …",
            "user2": "",
            "system": "Return mappings with unit IDs, keep placeholders.",
        },
        "metadata": {
            "user1": "Suggest categories/tags for this recipe …",
            "user2": "",
            "system": "Use the provided ID lists, return JSON {categoryId, tags:[…]}.",
        },
        "instructions": {
            "user1": "Ingredients (JSON): {ingredients}\nSteps (JSON): {steps}\nResponse format: {\"links\":[{\"stepId\":\"...\",\"ingredientIds\":[\"...\"]}]}",
            "user2": "",
            "system": (
                "You assign ingredients to preparation steps. "
                'Return JSON with field "links": [{stepId, ingredientIds[]}]. '
                "Use only provided IDs, no free text. Leave empty if nothing fits."
            ),
        },
        "foodForms": {
            "user1": (
                "Determine singular, plural, countability and strict aliases, then map every ingredient to an existing food category.\n"
                "Respond with JSON only.\n\n"
                "Ingredient list:\n{ingredient_lines}\n\n"
                "Available categories (ID – name):\n{category_lines}"
            ),
            "user2": "",
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
            "user1": (
                "Create suitable spellings for these units. Respond strictly as JSON in the described schema.\n\n"
                "{unit_lines}"
            ),
            "user2": "",
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


PROMPT_KEYS = ("user1", "user2", "system")


def _normalized_entry(entry: Dict[str, Any]) -> Dict[str, str]:
    """Normalize legacy prompt entries (free/system) into user1/user2/system."""
    normalized: Dict[str, str] = {}
    if not isinstance(entry, dict):
        return {"user1": "", "user2": "", "system": ""}
    # Legacy support: treat "free" as user1 when present.
    legacy_free = entry.get("free")
    if isinstance(legacy_free, str):
        normalized["user1"] = legacy_free
    for key in PROMPT_KEYS:
        value = entry.get(key)
        if isinstance(value, str):
            normalized[key] = value
    for key in PROMPT_KEYS:
        normalized.setdefault(key, "")
    return normalized


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
            normalized = _normalized_entry(values)
            module_entry.update(normalized)
    return merged


def _merge_llm_config(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = deepcopy(base)
    if not isinstance(override, dict):
        return merged
    for module, cfg in override.items():
        if not isinstance(cfg, dict):
            continue
        target = merged.setdefault(module, {})
        for key in ("model", "temperature", "top_p", "max_output_tokens"):
            if key in cfg:
                target[key] = cfg[key]
    return merged


def _load_prompt_file() -> tuple[Dict[str, Dict[str, Dict[str, str]]], Dict[str, Dict[str, Dict[str, str]]], Dict[str, Any]]:
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
        llm_section = data.get("llmConfig")
    else:
        defaults_section = None
        prompts_section = data if isinstance(data, dict) else None
        llm_section = None

    defaults = _merge_prompts(FALLBACK_DEFAULTS, defaults_section)
    prompts = _merge_prompts(defaults, prompts_section)
    llm_config = _merge_llm_config(LLM_CONFIG_DEFAULTS, llm_section)
    return defaults, prompts, llm_config


def load_prompts() -> Dict[str, Dict[str, Dict[str, str]]]:
    _, prompts, _ = _load_prompt_file()
    return prompts


def load_llm_config() -> Dict[str, Any]:
    _, _, llm_config = _load_prompt_file()
    return llm_config


def save_prompts(data: Dict[str, Dict[str, Dict[str, str]]]) -> None:
    defaults, _, llm_config = _load_prompt_file()
    normalized_prompts: Dict[str, Dict[str, Dict[str, str]]] = {}
    for locale, modules in (data or {}).items():
        if not isinstance(modules, dict):
            continue
        locale_entry: Dict[str, Dict[str, str]] = {}
        for module, entry in modules.items():
            if not isinstance(entry, dict):
                continue
            locale_entry[module] = _normalized_entry(entry)
        if locale_entry:
            normalized_prompts[locale] = locale_entry
    PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"defaults": defaults, "prompts": normalized_prompts, "llmConfig": llm_config}
    PROMPT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_llm_config(llm_config: Dict[str, Any]) -> None:
    defaults, prompts, _ = _load_prompt_file()
    merged = _merge_llm_config(LLM_CONFIG_DEFAULTS, llm_config)
    PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"defaults": defaults, "prompts": prompts, "llmConfig": merged}
    PROMPT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_prompt_defaults() -> Dict[str, Dict[str, Dict[str, str]]]:
    defaults, _, _ = _load_prompt_file()
    return deepcopy(defaults)


def _safe_format(text: str, replacements: Optional[Dict[str, str]]) -> str:
    if not replacements:
        return text
    class _DefaultDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"
    try:
        return text.format_map(_DefaultDict(replacements))
    except Exception:
        return text


def resolve_prompt(module: str, locale: Optional[str] = None, replacements: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Return the prompt texts for *module* using *locale* with fallbacks."""
    defaults, prompts, _ = _load_prompt_file()

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
            result = {
                "user1": _safe_format(found.get("user1", ""), replacements),
                "user2": _safe_format(found.get("user2", ""), replacements),
                "system": _safe_format(found.get("system", ""), replacements),
            }
            result["free"] = result["user1"]
            return result
    for loc in candidates:
        found = _lookup(defaults, loc)
        if found:
            result = {
                "user1": _safe_format(found.get("user1", ""), replacements),
                "user2": _safe_format(found.get("user2", ""), replacements),
                "system": _safe_format(found.get("system", ""), replacements),
            }
            result["free"] = result["user1"]
            return result
    return {"user1": "", "user2": "", "system": "", "free": ""}


def resolve_llm_config(module: str) -> Dict[str, Any]:
    _, _, llm_config = _load_prompt_file()
    defaults = LLM_CONFIG_DEFAULTS.get(module, {})
    cfg = llm_config.get(module, {}) if isinstance(llm_config, dict) else {}
    return {
        "model": cfg.get("model", defaults.get("model")),
        "temperature": cfg.get("temperature", defaults.get("temperature")),
        "top_p": cfg.get("top_p", defaults.get("top_p")),
        "max_output_tokens": cfg.get("max_output_tokens", defaults.get("max_output_tokens")),
    }
