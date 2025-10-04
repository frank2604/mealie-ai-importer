"""Helpers for keeping Mealie ingredient data in sync."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import httpx

try:  # pragma: no cover - rapidfuzz is optional during development
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback when rapidfuzz is unavailable
    fuzz = None  # type: ignore

from ..config import IngredientConfig
from ..llm_parser import OpenAiClient

logger = logging.getLogger(__name__)

_CACHE_FILENAME = "ingredients.json"
_FORMS_FILENAME = "ingredient_forms.json"
_DEFAULT_TIMEOUT = 30.0


@dataclass
class UnitResource:
    id: str
    raw: Dict[str, Any]

    @property
    def name(self) -> str:
        return self.raw.get("name", "")


@dataclass
class FoodResource:
    id: str
    raw: Dict[str, Any]

    @property
    def name(self) -> str:
        return self.raw.get("name", "")


class IngredientService:
    """Coordinate ingredient units, foods, and labels against the Mealie API."""

    def __init__(
        self,
        *,
        base_url: Optional[str],
        token: Optional[str],
        config: Optional[IngredientConfig] = None,
        llm_client: Optional[OpenAiClient] = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._token = token or ""
        self._config = config or IngredientConfig()
        self._llm_client = llm_client if self._config.use_llm_classifier else None

        self._cache_dir = self._config.cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_path = self._cache_dir / _CACHE_FILENAME
        self._forms_path = self._cache_dir / _FORMS_FILENAME

        self._units: List[Dict[str, Any]] = []
        self._foods: List[Dict[str, Any]] = []
        self._labels: List[Dict[str, Any]] = []
        self._forms: Dict[str, List[str]] = {}
        self._classification_cache: Dict[str, str] = {}

        self._enabled = bool(self._base_url and self._token)
        self._client: Optional[httpx.Client] = None
        if self._enabled:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            self._client = httpx.Client(base_url=self._base_url, headers=headers, timeout=_DEFAULT_TIMEOUT)

        self._load_local_cache()
        if self._enabled:
            self._ensure_remote_seed()

    def __bool__(self) -> bool:  # pragma: no cover - simple truthiness helper
        return self._enabled

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def close(self) -> None:
        if self._client:
            self._client.close()

    def refresh(self) -> None:
        """Force-refresh all cached resources from the API."""
        if not self._client:
            return
        self._units = self._fetch_paginated("/api/units")
        self._foods = self._fetch_paginated("/api/foods")
        self._labels = self._fetch_paginated("/api/groups/labels")
        self._save_cache()

    def get_or_create_unit(
        self,
        *,
        name: str,
        plural_name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        fraction: bool = True,
    ) -> UnitResource:
        if not name:
            raise ValueError("Unit name is required")

        existing = self._find_unit(name) or (abbreviation and self._find_unit(abbreviation))
        if existing:
            return UnitResource(id=existing["id"], raw=existing)

        payload = self._clean_payload(
            {
                "name": name,
                "pluralName": plural_name or name,
                "description": "",
                "extras": {},
                "fraction": fraction,
                "abbreviation": abbreviation or name,
                "pluralAbbreviation": abbreviation or plural_name or name,
                "useAbbreviation": bool(abbreviation),
                "aliases": [],
            }
        )

        created = self._create_remote("/api/units", payload, fallback=existing)
        if created:
            self._units.append(created)
            self._save_cache()
            return UnitResource(id=created["id"], raw=created)

        raise RuntimeError("Unit could not be created and is not cached")

    def get_or_create_food(
        self,
        *,
        name: str,
        description: str = "",
        category_hint: Optional[str] = None,
        aliases: Optional[Iterable[str]] = None,
    ) -> FoodResource:
        if not name:
            raise ValueError("Food name is required")

        existing = self._find_food(name)
        if existing:
            return FoodResource(id=existing["id"], raw=existing)

        label = self._ensure_label(self._pick_label_name(name, category_hint))
        singular, plural = self._infer_forms(name)
        payload = self._clean_payload(
            {
                "name": singular,
                "pluralName": plural,
                "description": description,
                "extras": {},
                "labelId": label["id"],
                "aliases": list(aliases or []),
                "householdsWithIngredientFood": [],
            }
        )

        created = self._create_remote("/api/foods", payload, fallback=existing)
        if created:
            self._foods.append(created)
            self._remember_forms(created["name"], singular, plural)
            self._save_cache()
            return FoodResource(id=created["id"], raw=created)

        raise RuntimeError("Food could not be created and is not cached")

    # ------------------------------------------------------------------
    # Cache bootstrap helpers
    # ------------------------------------------------------------------
    def _load_local_cache(self) -> None:
        if self._cache_path.exists():
            try:
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Konnte Ingredient-Cache nicht lesen, starte leer")
            else:
                self._units = list(data.get("units", []))
                self._foods = list(data.get("foods", []))
                self._labels = list(data.get("labels", []))

        if self._forms_path.exists():
            try:
                self._forms = json.loads(self._forms_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("Ingredient-Form-Cache beschädigt, ignoriere")
                self._forms = {}

    def _ensure_remote_seed(self) -> None:
        try:
            refreshed = False
            if not self._units:
                self._units = self._fetch_paginated("/api/units")
                refreshed = True
            if not self._foods:
                self._foods = self._fetch_paginated("/api/foods")
                refreshed = True
            if not self._labels:
                self._labels = self._fetch_paginated("/api/groups/labels")
                refreshed = True
            if refreshed:
                self._save_cache()
        except httpx.HTTPError as exc:
            logger.warning("Konnte Ingredient-Daten nicht von Mealie laden: %s", exc)

    def _fetch_paginated(self, endpoint: str, *, per_page: int = 200) -> List[Dict[str, Any]]:
        if not self._client:
            return []
        items: List[Dict[str, Any]] = []
        page = 1
        while True:
            response = self._client.get(endpoint, params={"page": page, "perPage": per_page})
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                items.extend(payload)
                break

            page_items = payload.get("items") or []
            items.extend(page_items)

            total_pages = payload.get("total_pages") or payload.get("totalPages") or 1
            next_link = payload.get("next")
            if page >= int(total_pages or 1) or not next_link:
                break
            page += 1
        return items

    def _save_cache(self) -> None:
        data = {
            "units": self._units,
            "foods": self._foods,
            "labels": self._labels,
        }
        self._cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._forms_path.write_text(json.dumps(self._forms, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def _find_unit(self, query: str) -> Optional[Dict[str, Any]]:
        return self._match_cached(query, self._units, ["name", "pluralName", "abbreviation", "pluralAbbreviation"])

    def _find_food(self, query: str) -> Optional[Dict[str, Any]]:
        fields = ["name", "pluralName"]
        match = self._match_cached(query, self._foods, fields)
        if match:
            return match
        # include aliases as secondary pass
        for food in self._foods:
            for alias in food.get("aliases", []) or []:
                if self._score(query, alias) >= self._config.fuzzy_threshold:
                    return food
        return None

    def _match_label(self, query: str) -> Optional[Dict[str, Any]]:
        return self._match_cached(query, self._labels, ["name"])

    def _match_cached(
        self,
        query: str,
        collection: Iterable[Dict[str, Any]],
        fields: Iterable[str],
    ) -> Optional[Dict[str, Any]]:
        normalized_query = self._normalize(query)
        if not normalized_query:
            return None

        best_item: Optional[Dict[str, Any]] = None
        best_score = 0
        threshold = max(0, min(100, self._config.fuzzy_threshold))

        for item in collection:
            # prefer exact matches before fuzzy logic
            for field in fields:
                value = item.get(field)
                if not value:
                    continue
                if self._normalize(str(value)) == normalized_query:
                    return item

            for field in fields:
                value = item.get(field)
                if not value:
                    continue
                score = self._score(query, str(value))
                if score > best_score:
                    best_score = score
                    best_item = item

        if best_item and best_score >= threshold:
            return best_item
        return None

    # ------------------------------------------------------------------
    # Label management
    # ------------------------------------------------------------------
    def _pick_label_name(self, ingredient_name: str, category_hint: Optional[str]) -> str:
        normalized_name = self._normalize(ingredient_name)
        if category_hint:
            match = self._match_label(category_hint)
            if match:
                return match["name"]

        heuristics = self._category_by_heuristic(normalized_name)
        if heuristics:
            return heuristics

        if normalized_name in self._classification_cache:
            return self._classification_cache[normalized_name]

        if self._llm_client:
            suggestion = self._classify_with_llm(ingredient_name, category_hint)
            if suggestion:
                self._classification_cache[normalized_name] = suggestion
                return suggestion

        default_label = self._config.default_category
        self._classification_cache[normalized_name] = default_label
        return default_label

    def _ensure_label(self, label_name: str) -> Dict[str, Any]:
        existing = self._match_label(label_name)
        if existing:
            return existing

        color = self._config.default_category_color
        payload = self._clean_payload({"name": label_name, "color": color})
        created = self._create_remote("/api/groups/labels", payload, fallback=existing)
        if created:
            self._labels.append(created)
            self._save_cache()
            return created

        raise RuntimeError("Label could not be created and is not cached")

    def _category_by_heuristic(self, normalized_name: str) -> Optional[str]:
        categories = {
            "fleisch": "Fleisch",
            "hähnchen": "Fleisch",
            "rind": "Fleisch",
            "schwein": "Fleisch",
            "speck": "Fleisch",
            "fisch": "Fisch & Meeresfrüchte",
            "lachs": "Fisch & Meeresfrüchte",
            "garnele": "Fisch & Meeresfrüchte",
            "krabbe": "Fisch & Meeresfrüchte",
            "milch": "Milchprodukte",
            "käse": "Milchprodukte",
            "butter": "Milchprodukte",
            "joghurt": "Milchprodukte",
            "sahne": "Milchprodukte",
            "quark": "Milchprodukte",
            "reis": "Getreide & Hülsenfrüchte",
            "nudel": "Getreide & Hülsenfrüchte",
            "mehl": "Backzutaten",
            "linse": "Getreide & Hülsenfrüchte",
            "bohne": "Getreide & Hülsenfrüchte",
            "kartoff": "Obst & Gemüse",
            "zwiebel": "Obst & Gemüse",
            "paprika": "Obst & Gemüse",
            "apfel": "Obst & Gemüse",
            "salat": "Obst & Gemüse",
            "beere": "Obst & Gemüse",
            "banane": "Obst & Gemüse",
            "gewürz": "Gewürze",
            "salz": "Gewürze",
            "pfeffer": "Gewürze",
            "curry": "Gewürze",
            "zucker": "Süßwaren",
            "honig": "Süßwaren",
            "schokolade": "Süßwaren",
            "wein": "Getränke",
            "bier": "Getränke",
            "rum": "Alkohol",
        }
        for token, label in categories.items():
            if token in normalized_name:
                return label
        return None

    def _classify_with_llm(self, ingredient_name: str, category_hint: Optional[str]) -> Optional[str]:
        if not self._llm_client:
            return None

        label_names = ", ".join(sorted({label["name"] for label in self._labels} or {self._config.default_category}))
        system_prompt = (
            "Du ordnest Lebensmittel kurzen Kategorien zu. "
            "Verwende ausschließlich eine der vorhandenen Kategorien und antworte nur mit dem Namen."
        )
        user_prompt = (
            "Verfügbare Kategorien: "
            f"{label_names}\n"
            f"Zutat: {ingredient_name}\n"
            f"Rezeptkategorie: {category_hint or 'unbekannt'}\n"
            "Antworte ausschließlich mit einer Kategorie aus der Liste."
        )
        try:
            response = self._llm_client.run_text(system_prompt, user_prompt).strip()
        except Exception as exc:  # pragma: no cover - external dependency
            logger.debug("LLM Klassifikation fehlgeschlagen: %s", exc)
            return None
        cleaned = response.splitlines()[0].strip().strip("'\"")
        if cleaned:
            return cleaned
        return None

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _create_remote(
        self,
        endpoint: str,
        payload: Mapping[str, Any],
        *,
        fallback: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self._client:
            return fallback
        try:
            response = self._client.post(endpoint, json=payload)
            if response.status_code == 409 and fallback:
                logger.debug("Resource already existed for %s", payload)
                return fallback
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            if fallback:
                logger.debug("Verwende Cache-Eintrag nach Fehlschlag %s: %s", endpoint, exc)
                return fallback
            logger.error("Anfrage an %s fehlgeschlagen (%s): %s", endpoint, exc.response.status_code, exc)
            raise
        except httpx.HTTPError as exc:
            if fallback:
                logger.debug("HTTP-Fehler für %s, benutze Cache: %s", endpoint, exc)
                return fallback
            logger.error("HTTP-Fehler für %s: %s", endpoint, exc)
            raise

    def _infer_forms(self, base: str) -> Tuple[str, str]:
        name = base.strip()
        if not name:
            return "", ""

        key = self._forms_key(name)
        cached = self._forms.get(key)
        if cached and len(cached) == 2:
            return cached[0], cached[1]

        normalized = self._normalize(name)
        for forms in self._forms.values():
            if len(forms) != 2:
                continue
            singular_cached, plural_cached = forms
            if normalized == self._normalize(singular_cached) or normalized == self._normalize(plural_cached):
                return singular_cached, plural_cached

        for food in self._foods:
            singular_cached = food.get("name") or ""
            plural_cached = food.get("pluralName") or singular_cached
            if not singular_cached:
                continue
            if normalized == self._normalize(singular_cached) or (
                plural_cached and normalized == self._normalize(plural_cached)
            ):
                return singular_cached, plural_cached

        def apply_rules(word: str) -> Tuple[str, str]:
            lower_word = word.lower()
            if lower_word.endswith(("chen", "lein")):
                return word, word
            if lower_word.endswith("en") and len(word) > 2:
                return word[:-1], word
            if lower_word.endswith("n") and len(word) > 1:
                return word[:-1], word
            if lower_word.endswith("e"):
                return word, word + "n"
            if lower_word.endswith(("er", "el", "s")):
                return word, word
            return word, word + "e"

        match = re.search(r"([A-Za-zÄÖÜäöüß]+)$", name)
        if match:
            start = match.start(1)
            prefix = name[:start]
            stem = match.group(1)
            singular_stem, plural_stem = apply_rules(stem)
            singular = f"{prefix}{singular_stem}"
            plural = f"{prefix}{plural_stem}"
        else:
            singular, plural = apply_rules(name)

        return singular, plural

    def _remember_forms(self, name: str, singular: str, plural: str) -> None:
        key = self._forms_key(name)
        self._forms[key] = [singular, plural]

    def _forms_key(self, name: str) -> str:
        return f"v2:Lebensmittel:{self._slugify(name)}"

    def _normalize(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value or "").strip().lower()
        return normalized

    def _score(self, left: str, right: str) -> int:
        if fuzz:
            return int(fuzz.ratio(left, right))
        return 100 if self._normalize(left) == self._normalize(right) else 0

    @staticmethod
    def _slugify(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    @staticmethod
    def _clean_payload(data: Mapping[str, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, str) and value == "":
                continue
            cleaned[key] = value
        return cleaned


__all__ = ["IngredientService", "FoodResource", "UnitResource"]
