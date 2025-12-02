"""Helpers for keeping Mealie ingredient data in sync."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, Union

import httpx

try:  # pragma: no cover - rapidfuzz is optional during development
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback when rapidfuzz is unavailable
    fuzz = None  # type: ignore

from ..config import IngredientConfig
from ..exceptions import UserAbort
from ..llm_parser import OpenAiClient
from ..prompt_store import resolve_prompt, resolve_llm_config
from ..prompt_logging import log_prompt_messages
from ..llm_utils import format_llm_log

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_MAX_FORM_BATCH = 12

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


@dataclass
class FoodForms:
    singular: str
    plural: str
    countable: bool
    aliases: List[str]
    label_id: Optional[str] = None
    label_name: Optional[str] = None


@dataclass
class UnitForms:
    name: str
    plural_name: Optional[str]
    abbreviation: Optional[str]
    plural_abbreviation: Optional[str]
    use_abbreviation: bool = False


class IngredientService:
    """Coordinate ingredient units, foods, and labels against the Mealie API."""

    def __init__(
        self,
        *,
        base_url: Optional[str],
        token: Optional[str],
        config: Optional[IngredientConfig] = None,
        llm_client: Optional[OpenAiClient] = None,
        verify: Union[bool, str] = True,
        auto_seed: bool = True,
        prompt_locale: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._token = token or ""
        self._config = config or IngredientConfig()
        self._llm_client = llm_client
        self._verify = verify

        self._cache_dir = self._config.cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._recipe_categories_path = self._cache_dir / "MealieRecipeCategoriesCache.json"
        self._tags_path = self._cache_dir / "MealieTagsCache.json"
        self._tag_categories_path = self._cache_dir / "MealieTagCategoriesCache.json"
        self._foods_path = self._cache_dir / "MealieFoodsCache.json"
        self._food_categories_path = self._cache_dir / "MealieFoodCategoriesCache.json"
        self._units_path = self._cache_dir / "MealieUnitsCache.json"

        self._units: List[Dict[str, Any]] = []
        self._foods: List[Dict[str, Any]] = []
        self._labels: List[Dict[str, Any]] = []
        self._recipe_categories: List[Dict[str, Any]] = []
        self._tags: List[Dict[str, Any]] = []
        self._tag_categories: List[str] = []
        self._forms_cache: Dict[str, FoodForms] = {}
        self._unit_forms_cache: Dict[str, UnitForms] = {}
        self._prompt_locale = (prompt_locale or "de") or "de"

        self._enabled = bool(self._base_url and self._token)
        self._client: Optional[httpx.Client] = None
        if self._enabled:
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            self._client = httpx.Client(
                base_url=self._base_url,
                headers=headers,
                timeout=_DEFAULT_TIMEOUT,
                verify=self._verify,
            )

        self._load_local_cache()
        if self._enabled and auto_seed:
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
        self.refresh_units(save=False)
        self.refresh_foods(save=False)
        self.refresh_recipe_categories(save=False)
        self.refresh_tags(save=False)
        self._save_cache()

    def refresh_units(self, *, save: bool = True) -> None:
        if not self._client:
            return
        self._units = self._fetch_paginated("/api/units")
        if save:
            self._save_cache()

    def refresh_foods(self, *, save: bool = True) -> None:
        if not self._client:
            return
        self._foods = self._fetch_paginated("/api/foods")
        self._labels = self._fetch_paginated("/api/groups/labels")
        if save:
            self._save_cache()

    def refresh_recipe_categories(self, *, save: bool = True) -> None:
        if not self._client:
            return
        self._recipe_categories = self._fetch_paginated("/api/organizers/categories")
        if save:
            self._save_cache()

    def refresh_tags(self, *, save: bool = True) -> None:
        if not self._client:
            return
        self._tags = self._fetch_paginated("/api/organizers/tags")
        self._tag_categories = self._extract_tag_categories(self._tags)
        if save:
            self._save_cache()

    def list_units(self) -> List[Dict[str, Any]]:
        return list(self._units)

    def list_foods(self) -> List[Dict[str, Any]]:
        return list(self._foods)

    def list_food_categories(self) -> List[Dict[str, Any]]:
        return list(self._labels)

    def list_recipe_categories(self) -> List[Dict[str, Any]]:
        return list(self._recipe_categories)

    def list_tags(self) -> List[Dict[str, Any]]:
        return list(self._tags)

    def list_tag_categories(self) -> List[str]:
        if not self._tag_categories:
            self._tag_categories = self._extract_tag_categories(self._tags)
        return list(self._tag_categories)

    def lookup_unit(self, query: str) -> Optional[UnitResource]:
        match = self._find_unit(query)
        if match:
            return UnitResource(id=str(match.get("id")), raw=match)
        return None

    def lookup_food(self, query: str) -> Optional[FoodResource]:
        match = self._find_food(query)
        if match:
            return FoodResource(id=str(match.get("id")), raw=match)
        return None

    def get_unit_by_id(self, unit_id: str) -> Optional[UnitResource]:
        for item in self._units:
            if str(item.get("id")) == str(unit_id):
                return UnitResource(id=str(item.get("id")), raw=item)
        return None

    def get_food_by_id(self, food_id: str) -> Optional[FoodResource]:
        for item in self._foods:
            if str(item.get("id")) == str(food_id):
                return FoodResource(id=str(item.get("id")), raw=item)
        return None

    def get_or_create_unit(
        self,
        *,
        name: str,
        plural_name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        fraction: bool = True,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> UnitResource:
        if not name:
            raise ValueError("Unit name is required")

        existing = self._find_unit(name) or (abbreviation and self._find_unit(abbreviation))
        if existing:
            return UnitResource(id=existing["id"], raw=existing)

        forms = self._infer_unit_forms(
            base=name,
            debug=debug,
            confirm=confirm,
        )
        unit_name = forms.name or name
        plural_form = forms.plural_name or plural_name or unit_name
        abbreviation_value = forms.abbreviation or abbreviation
        plural_abbreviation_candidate = forms.plural_abbreviation or abbreviation_value
        plural_abbreviation = self._clean_plural_abbreviation(
            singular=unit_name,
            plural=plural_form,
            abbreviation=abbreviation_value,
            plural_abbreviation=plural_abbreviation_candidate,
        )

        payload = self._clean_payload(
            {
                "name": unit_name,
                "pluralName": plural_form,
                "description": "",
                "extras": {},
                "fraction": fraction,
                "abbreviation": abbreviation_value,
                "pluralAbbreviation": plural_abbreviation,
                "useAbbreviation": bool(abbreviation_value) and forms.use_abbreviation,
                "aliases": [],
            }
        )

        self._debug_write(
            debug,
            "post_unit_request",
            {
                "name": unit_name,
                "payload": payload,
            },
        )

        if not self._client:
            created = self._create_remote("/api/units", payload, fallback=existing)
        else:
            try:
                response = self._client.post("/api/units", json=payload)
            except httpx.HTTPError as exc:
                self._debug_write(
                    debug,
                    "post_unit_response_error",
                    {"name": unit_name, "error": str(exc)},
                )
                raise

            self._debug_write(
                debug,
                "post_unit_response",
                {
                    "name": unit_name,
                    "response": self._response_debug_payload(response),
                },
            )

            if response.status_code == 409 and existing:
                return UnitResource(id=existing["id"], raw=existing)

            response.raise_for_status()
            created = response.json()
        if created:
            self._units.append(created)
            self._save_cache()
            return UnitResource(id=created["id"], raw=created)

        raise RuntimeError("Unit could not be created and is not cached")

    def create_unit_manual(
        self,
        *,
        name: str,
        plural_name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        plural_abbreviation: Optional[str] = None,
        use_abbreviation: bool = False,
        debug: Optional[Any] = None,
    ) -> UnitResource:
        if not name:
            raise ValueError("Unit name is required")

        payload = self._clean_payload(
            {
                "name": name,
                "pluralName": plural_name or name,
                "description": "",
                "extras": {},
                "fraction": True,
                "abbreviation": abbreviation,
                "pluralAbbreviation": plural_abbreviation,
                "useAbbreviation": bool(abbreviation) and use_abbreviation,
                "aliases": [],
            }
        )

        self._debug_write(
            debug,
            "post_unit_manual_request",
            {
                "name": name,
                "payload": payload,
            },
        )

        created = self._create_remote("/api/units", payload)
        if not created:
            raise RuntimeError("Manual unit creation failed")

        self._units.append(created)
        self._save_cache()
        return UnitResource(id=created["id"], raw=created)

    def unit_form_suggestions(
        self,
        names: Iterable[str],
        *,
        debug: Optional[Any] = None,
    ) -> Dict[str, Dict[str, Any]]:
        suggestions: Dict[str, Dict[str, Any]] = {}
        for raw_name in names:
            base = (raw_name or "").strip()
            if not base:
                continue
            forms = self._infer_unit_forms(base, debug=debug)
            suggestions[base] = {
                "name": forms.name or base,
                "pluralName": forms.plural_name or forms.name or base,
                "abbreviation": forms.abbreviation,
                "pluralAbbreviation": forms.plural_abbreviation,
                "useAbbreviation": forms.use_abbreviation,
            }
        return suggestions

    def get_or_create_food(
        self,
        *,
        name: str,
        description: str = "",
        category_hint: Optional[str] = None,
        aliases: Optional[Iterable[str]] = None,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> FoodResource:
        if not name:
            raise ValueError("Food name is required")

        existing = self._find_food(name)
        if existing:
            self._debug_write(
                debug,
                "food_existing",
                {"ingredient": name, "foodId": existing.get("id")},
            )
            return FoodResource(id=existing["id"], raw=existing)

        forms = self._infer_forms(name)
        self._debug_write(
            debug,
            "food_forms_applied",
            {"ingredient": name, "forms": self._forms_to_dict(forms)},
        )
        label: Optional[Dict[str, Any]] = None
        if forms.label_id:
            label = self._label_by_id(forms.label_id)
            if not label:
                logger.warning(
                    "LLM lieferte unbekannte Kategorie-ID %s für '%s'",
                    forms.label_id,
                    name,
                )
                forms.label_id = None
        if not label and forms.label_name:
            label = self._match_label(forms.label_name)
            if not label:
                forms.label_name = None

        if label:
            resolved_id = str(label.get("id") or "").strip()
            resolved_name = str(label.get("name") or "").strip()
            if resolved_id:
                forms.label_id = resolved_id
            if resolved_name:
                forms.label_name = resolved_name
        singular = self._capitalize_first(forms.singular)
        plural = self._capitalize_first(forms.plural)
        alias_strings = self._merge_aliases(forms.aliases, aliases, singular=singular, plural=plural)
        alias_payload = [{"name": alias} for alias in alias_strings]
        payload = self._clean_payload(
            {
                "name": singular,
                "pluralName": plural,
                "description": description,
                "extras": {},
                "labelId": label["id"] if label else None,
                "aliases": alias_payload,
                "householdsWithIngredientFood": [],
            }
        )

        self._debug_write(
            debug,
            "post_food_request",
            {
                "ingredient": name,
                "payload": payload,
            },
        )

        if not self._client:
            created = self._create_remote("/api/foods", payload, fallback=existing)
        else:
            self._maybe_confirm(confirm, f"POST /api/foods – {singular}")
            try:
                response = self._client.post("/api/foods", json=payload)
            except httpx.HTTPError as exc:
                self._debug_write(
                    debug,
                    "post_food_response_error",
                    {"ingredient": name, "error": str(exc)},
                )
                raise

            self._debug_write(
                debug,
                "post_food_response",
                {
                    "ingredient": name,
                    "response": self._response_debug_payload(response),
                },
            )

            if response.status_code == 409:
                fallback = self._find_food(name)
                if fallback:
                    self._debug_write(
                        debug,
                        "food_existing_after_conflict",
                        {"ingredient": name, "foodId": fallback.get("id")},
                    )
                    return FoodResource(id=fallback["id"], raw=fallback)

            response.raise_for_status()
            created = response.json()

        if created:
            self._foods.append(created)
            normalized = self._normalize(name)
            if normalized not in self._forms_cache:
                self._forms_cache[normalized] = forms
            return FoodResource(id=created["id"], raw=created)

        raise RuntimeError("Food could not be created and is not cached")

    def create_food_manual(
        self,
        *,
        name_singular: str,
        name_plural: Optional[str],
        category_id: Optional[str] = None,
        aliases: Optional[Iterable[str]] = None,
        description: str = "",
        debug: Optional[Any] = None,
    ) -> FoodResource:
        if not name_singular:
            raise ValueError("Food name is required")

        singular = self._capitalize_first(name_singular)
        plural = self._capitalize_first(name_plural or name_singular)
        alias_list = [
            {"name": str(alias)} for alias in (aliases or []) if isinstance(alias, str) and alias
        ]
        payload = self._clean_payload(
            {
                "name": singular,
                "pluralName": plural,
                "description": description,
                "extras": {},
                "labelId": category_id,
                "aliases": alias_list,
                "householdsWithIngredientFood": [],
            }
        )

        self._debug_write(
            debug,
            "post_food_manual_request",
            {
                "name": singular,
                "payload": payload,
            },
        )

        created = self._create_remote("/api/foods", payload)
        if not created:
            raise RuntimeError("Manual food creation failed")

        self._foods.append(created)
        self._save_cache()
        return FoodResource(id=created["id"], raw=created)

    def food_form_suggestions(
        self,
        names: Iterable[str],
        *,
        debug: Optional[Any] = None,
    ) -> Dict[str, Dict[str, Any]]:
        suggestions: Dict[str, Dict[str, Any]] = {}
        for raw_name in names:
            name = (raw_name or "").strip()
            if not name:
                continue
            forms = self._infer_forms(name)
            self._debug_write(
                debug,
                "food_forms_proposed",
                {"ingredient": name, "forms": self._forms_to_dict(forms)},
            )
            suggestions[name] = {
                "nameSingular": self._capitalize_first(forms.singular),
                "namePlural": self._capitalize_first(forms.plural),
                "aliases": list(forms.aliases),
                "categoryId": forms.label_id,
                "categoryName": forms.label_name,
            }
        return suggestions

    def prepare_food_forms(
        self,
        names: Iterable[str],
        *,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> None:
        pending: List[str] = []
        for raw_name in names:
            name = (raw_name or "").strip()
            if not name:
                continue
            normalized = self._normalize(name)
            if normalized in self._forms_cache:
                self._debug_write(
                    debug,
                    "food_forms_cached",
                    {"ingredient": name, "forms": self._forms_to_dict(self._forms_cache[normalized])},
                )
                continue
            existing = self._forms_from_existing(normalized)
            if existing:
                self._forms_cache[normalized] = existing
                self._debug_write(
                    debug,
                    "food_forms_existing",
                    {
                        "ingredient": name,
                        "forms": self._forms_to_dict(existing),
                        "source": "existing_food",
                    },
                )
                continue
            pending.append(name)

        if not pending:
            return

        categories = self._llm_category_choices()

        if self._config.use_llm_forms and self._llm_client:
            generated = self._generate_forms_with_llm(
                pending,
                categories=categories,
                debug=debug,
                confirm=confirm,
            )
            for name in pending:
                normalized = self._normalize(name)
                if normalized in generated:
                    self._debug_write(
                        debug,
                        "food_forms_llm",
                        {
                            "ingredient": name,
                            "forms": self._forms_to_dict(generated[normalized]),
                        },
                    )

        for name in pending:
            normalized = self._normalize(name)
            if normalized not in self._forms_cache:
                fallback = self._heuristic_forms(name)
                self._forms_cache[normalized] = fallback
                self._debug_write(
                    debug,
                    "food_forms_heuristic",
                    {"ingredient": name, "forms": self._forms_to_dict(fallback)},
                )

    def prepare_unit_forms(
        self,
        names: Iterable[str],
        *,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> None:
        pending: List[str] = []
        for raw_name in names:
            name = (raw_name or "").strip()
            normalized = self._normalize(name)
            if not normalized:
                continue
            if normalized in self._unit_forms_cache:
                continue
            existing = self._forms_from_existing_unit(normalized)
            if existing:
                self._unit_forms_cache[normalized] = existing
                continue
            pending.append(name)

        if not pending:
            return

        generated = self._generate_unit_forms(
            pending,
            debug=debug,
            confirm=confirm,
        )
        for name in pending:
            normalized = self._normalize(name)
            if normalized not in self._unit_forms_cache and normalized in generated:
                self._unit_forms_cache[normalized] = generated[normalized]

    def _llm_category_choices(self) -> List[Dict[str, str]]:
        choices: List[Dict[str, str]] = []
        for label in self._labels:
            label_id = str(label.get("id") or "").strip()
            name = str(label.get("name") or "").strip()
            if label_id and name:
                choices.append({"id": label_id, "name": name})
        return choices

    # ------------------------------------------------------------------
    # Cache bootstrap helpers
    # ------------------------------------------------------------------
    def _load_local_cache(self) -> None:
        if self._foods_path.exists():
            try:
                payload = json.loads(self._foods_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("Foods-Cache beschädigt, ignoriere")
            else:
                if isinstance(payload, dict):
                    foods = payload.get("foods") or payload.get("items") or []
                elif isinstance(payload, list):
                    foods = payload
                else:
                    foods = []
                self._foods = list(foods)

        if self._food_categories_path.exists():
            try:
                payload = json.loads(self._food_categories_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("FoodCategories-Cache beschädigt, ignoriere")
            else:
                if isinstance(payload, dict):
                    labels = payload.get("categories") or payload.get("items") or []
                elif isinstance(payload, list):
                    labels = payload
                else:
                    labels = []
                self._labels = list(labels)

        if self._units_path.exists():
            try:
                payload = json.loads(self._units_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("Units-Cache beschädigt, ignoriere")
            else:
                if isinstance(payload, dict):
                    units = payload.get("units") or payload.get("items") or []
                elif isinstance(payload, list):
                    units = payload
                else:
                    units = []
                self._units = list(units)

        if self._recipe_categories_path.exists():
            try:
                payload = json.loads(self._recipe_categories_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("RecipeCategories-Cache beschädigt, ignoriere")
            else:
                if isinstance(payload, dict):
                    categories = payload.get("categories") or payload.get("items") or []
                elif isinstance(payload, list):
                    categories = payload
                else:
                    categories = []
                self._recipe_categories = list(categories)

        if self._tags_path.exists():
            try:
                payload = json.loads(self._tags_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("Tags-Cache beschädigt, ignoriere")
            else:
                if isinstance(payload, dict):
                    tags = payload.get("tags") or payload.get("items") or []
                elif isinstance(payload, list):
                    tags = payload
                else:
                    tags = []
                self._tags = list(tags)

        if self._tag_categories_path.exists():
            try:
                payload = json.loads(self._tag_categories_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.debug("TagCategories-Cache beschädigt, ignoriere")
            else:
                if isinstance(payload, dict):
                    categories = payload.get("categories") or []
                elif isinstance(payload, list):
                    categories = payload
                else:
                    categories = []
                self._tag_categories = [str(item) for item in categories if str(item).strip()]

        if not self._tag_categories and self._tags:
            self._tag_categories = self._extract_tag_categories(self._tags)

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
            if not self._recipe_categories:
                self._recipe_categories = self._fetch_paginated("/api/organizers/categories")
                refreshed = True
            if not self._tags:
                self._tags = self._fetch_paginated("/api/organizers/tags")
                refreshed = True
            if not self._tag_categories and self._tags:
                self._tag_categories = self._extract_tag_categories(self._tags)
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
        self._save_organizer_cache()
        self._save_foods_cache()
        self._save_units_cache()

    def _save_organizer_cache(self) -> None:
        timestamp = datetime.utcnow().isoformat()
        categories_payload = {
            "updated_at": timestamp,
            "categories": self._recipe_categories,
        }
        self._recipe_categories_path.write_text(
            json.dumps(categories_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        tags_payload = {
            "updated_at": timestamp,
            "tags": self._tags,
        }
        self._tags_path.write_text(
            json.dumps(tags_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        tag_categories_payload = {
            "updated_at": timestamp,
            "categories": self._tag_categories or self._extract_tag_categories(self._tags),
        }
        self._tag_categories_path.write_text(
            json.dumps(tag_categories_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_foods_cache(self) -> None:
        timestamp = datetime.utcnow().isoformat()
        foods_payload = {
            "updated_at": timestamp,
            "foods": self._foods,
        }
        self._foods_path.write_text(
            json.dumps(foods_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        food_categories_payload = {
            "updated_at": timestamp,
            "categories": self._labels,
        }
        self._food_categories_path.write_text(
            json.dumps(food_categories_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_units_cache(self) -> None:
        timestamp = datetime.utcnow().isoformat()
        units_payload = {
            "updated_at": timestamp,
            "units": self._units,
        }
        self._units_path.write_text(
            json.dumps(units_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
                alias_value = alias.get("name") if isinstance(alias, Mapping) else alias
                if not isinstance(alias_value, str):
                    continue
                if self._score(query, alias_value) >= self._config.fuzzy_threshold:
                    return food
        return None

    def _extract_tag_categories(self, tags: Iterable[Dict[str, Any]]) -> List[str]:
        categories: set[str] = set()
        for tag in tags:
            name = str(tag.get("name") or "")
            if not name:
                continue
            if "|" in name:
                category = name.split("|", 1)[0].strip()
                if category:
                    categories.add(category)
        return sorted(categories)

    def _match_label(self, query: str) -> Optional[Dict[str, Any]]:
        return self._match_cached(query, self._labels, ["name"])

    def _label_by_id(self, label_id: str) -> Optional[Dict[str, Any]]:
        for label in self._labels:
            if str(label.get("id")) == str(label_id):
                return label
        return None

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
                candidate_value = str(value)
                if self._normalize(candidate_value) == normalized_query:
                    return item
                if self._normalize_strict(candidate_value) == normalized_query:
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

    def _infer_forms(self, base: str) -> FoodForms:
        name = (base or "").strip()
        if not name:
            return FoodForms("", "", True, [])

        normalized = self._normalize(name)
        cached = self._forms_cache.get(normalized)
        if cached:
            return cached

        existing = self._forms_from_existing(normalized)
        if existing:
            self._forms_cache[normalized] = existing
            return existing

        if self._config.use_llm_forms and self._llm_client:
            categories = self._llm_category_choices()
            llm_results = self._generate_forms_with_llm([name], categories=categories)
            if normalized in llm_results:
                result = llm_results[normalized]
                self._forms_cache[normalized] = result
                return result

        fallback = self._heuristic_forms(name)
        self._forms_cache[normalized] = fallback
        return fallback

    def _infer_unit_forms(
        self,
        base: str,
        *,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> UnitForms:
        name = (base or "").strip()
        if not name:
            return UnitForms("", None, None, None, False)

        normalized = self._normalize(name)
        cached = self._unit_forms_cache.get(normalized)
        if cached:
            return cached

        existing = self._forms_from_existing_unit(normalized)
        if existing:
            self._unit_forms_cache[normalized] = existing
            return existing

        if self._config.use_llm_forms and self._llm_client:
            generated = self._generate_unit_forms([name], debug=debug, confirm=confirm)
            if normalized in generated:
                forms = generated[normalized]
                self._unit_forms_cache[normalized] = forms
                return forms

        logger.warning("LLM konnte keine Einheit ableiten für '%s' – verwende einfache Standardwerte", name)
        fallback = UnitForms(
            name=self._capitalize_first(name),
            plural_name=name,
            abbreviation=None,
            plural_abbreviation=None,
            use_abbreviation=False,
        )
        self._unit_forms_cache[normalized] = fallback
        return fallback

    def _forms_from_existing(self, normalized_name: str) -> Optional[FoodForms]:
        if not normalized_name:
            return None
        for food in self._foods:
            singular = (food.get("name") or "").strip()
            plural = (food.get("pluralName") or singular or "").strip()
            if not singular:
                continue
            candidate_keys = {self._normalize(singular)}
            if plural:
                candidate_keys.add(self._normalize(plural))
            alias_strings = self._extract_alias_strings(food)
            for alias in alias_strings:
                candidate_keys.add(self._normalize(alias))
            if normalized_name in candidate_keys:
                label_id = str(food.get("labelId") or "").strip() or None
                label_name = None
                if label_id:
                    label = self._label_by_id(label_id)
                    if label:
                        label_name = str(label.get("name") or "").strip() or None
                alias_list = [
                    value
                    for value in (self._sanitize_alias_value(alias) for alias in alias_strings)
                    if value and value not in {self._normalize(singular), self._normalize(plural)}
                ]
                countable = self._normalize(singular) != self._normalize(plural)
                if not plural:
                    plural = singular
                return FoodForms(
                    singular=singular,
                    plural=plural,
                    countable=countable,
                    aliases=alias_list,
                    label_id=label_id,
                    label_name=label_name,
                )
        return None

    def _heuristic_forms(self, name: str) -> FoodForms:
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

        if self._normalize(singular) == self._normalize(plural):
            countable = False
            plural = singular
        else:
            countable = True
        return FoodForms(singular=singular, plural=plural, countable=countable, aliases=[])

    def _forms_from_existing_unit(self, normalized_name: str) -> Optional[UnitForms]:
        if not normalized_name:
            return None
        for unit in self._units:
            name = str(unit.get("name") or "").strip()
            plural = str(unit.get("pluralName") or "").strip() or None
            abbreviation = str(unit.get("abbreviation") or "").strip() or None
            plural_abbreviation = str(unit.get("pluralAbbreviation") or "").strip() or None
            candidates = {
                self._normalize(name),
            }
            if plural:
                candidates.add(self._normalize(plural))
            if abbreviation:
                candidates.add(self._normalize(abbreviation))
            if plural_abbreviation:
                candidates.add(self._normalize(plural_abbreviation))
            if normalized_name in candidates:
                plural_abbreviation = self._clean_plural_abbreviation(
                    singular=name,
                    plural=plural,
                    abbreviation=abbreviation,
                    plural_abbreviation=plural_abbreviation,
                )
                return UnitForms(
                    name=self._capitalize_first(name) if name else name,
                    plural_name=plural,
                    abbreviation=abbreviation,
                    plural_abbreviation=plural_abbreviation,
                    use_abbreviation=bool(abbreviation),
                )
        return None

    def _generate_forms_with_llm(
        self,
        names: Iterable[str],
        *,
        categories: List[Dict[str, str]],
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, FoodForms]:
        if not (self._config.use_llm_forms and self._llm_client):
            return {}

        pending: List[str] = []
        for raw_name in names:
            name = (raw_name or "").strip()
            normalized = self._normalize(name)
            if not normalized:
                continue
            if normalized in self._forms_cache:
                continue
            pending.append(name)

        if not pending:
            return {}

        results: Dict[str, FoodForms] = {}
        queue = pending[:]
        while queue:
            batch = queue[:_MAX_FORM_BATCH]
            del queue[:_MAX_FORM_BATCH]
            batch_results = self._run_forms_batch(
                batch,
                categories=categories,
                debug=debug,
                confirm=confirm,
            )
            results.update(batch_results)
            for key, forms in batch_results.items():
                self._forms_cache[key] = forms
        return results

    def _run_forms_batch(
        self,
        batch: List[str],
        *,
        categories: List[Dict[str, str]],
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, FoodForms]:
        if not batch:
            return {}

        try:
            category_lines = "\n".join(f"- {item['id']}: {item['name']}" for item in categories) or "- keine Kategorien vorhanden"
            replacements = {
                "ingredient_lines": "\n".join(batch),
                "category_lines": category_lines,
            }
            prompt_cfg = resolve_prompt("foodForms", self._prompt_locale, replacements=replacements)
            llm_cfg = resolve_llm_config("foodForms")
            supports_fn = (
                (lambda model: self._llm_client._supports_sampling_params(model))  # type: ignore[attr-defined]
                if self._llm_client
                else None
            )
            logger.info("LLM config (foodForms): %s", format_llm_log(llm_cfg, None, supports_fn))
            user_parts = [
                part.strip()
                for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
                if part and part.strip()
            ]
            user_prompt = "\n\n".join(user_parts).strip() or "\n".join(replacements.values())

            system_prompt = prompt_cfg.get("system") or ""

            log_prompt_messages(
                "foodForms",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            self._maybe_confirm(confirm, f"LLM Zutatenformen – {', '.join(batch)}")
            self._debug_write(
                debug,
                "foods_llm_request",
                {
                    "batch": batch,
                    "systemPrompt": system_prompt,
                    "userPrompt": user_prompt,
                    "categories": categories,
                },
            )
            llm_cfg = resolve_llm_config("foodForms")
            response = self._llm_client.run_json(system_prompt, user_prompt, llm_config=llm_cfg)
            self._debug_write(
                debug,
                "foods_llm_response",
                {
                    "batch": batch,
                    "response": response,
                },
            )
        except UserAbort:
            raise
        except Exception as exc:  # pragma: no cover - external dependency
            logger.warning("LLM konnte Formen nicht bestimmen (%s): %s", ", ".join(batch), exc)
            self._debug_write(
                debug,
                "foods_llm_response_error",
                {
                    "batch": batch,
                    "error": str(exc),
                },
            )
            return {}

        requested = {self._normalize(name): name for name in batch if self._normalize(name)}
        return self._parse_form_response(response, requested, categories, debug=debug)

    def _generate_unit_forms(
        self,
        names: Iterable[str],
        *,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, UnitForms]:
        if not (self._config.use_llm_forms and self._llm_client):
            return {}

        pending: List[str] = []
        for raw_name in names:
            name = (raw_name or "").strip()
            normalized = self._normalize(name)
            if not normalized:
                continue
            if normalized in self._unit_forms_cache:
                continue
            pending.append(name)

        if not pending:
            return {}

        results: Dict[str, UnitForms] = {}
        queue = pending[:]
        while queue:
            batch = queue[:_MAX_FORM_BATCH]
            del queue[:_MAX_FORM_BATCH]
            batch_results = self._run_unit_forms_batch(
                batch,
                debug=debug,
                confirm=confirm,
            )
            results.update(batch_results)
            for key, forms in batch_results.items():
                self._unit_forms_cache[key] = forms
        return results

    def _run_unit_forms_batch(
        self,
        batch: List[str],
        *,
        debug: Optional[Any] = None,
        confirm: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, UnitForms]:
        if not batch:
            return {}

        try:
            replacements = {"unit_lines": "\n".join(batch)}
            prompt_cfg = resolve_prompt("unitForms", self._prompt_locale, replacements=replacements)
            llm_cfg = resolve_llm_config("unitForms")
            supports_fn = (
                (lambda model: self._llm_client._supports_sampling_params(model))  # type: ignore[attr-defined]
                if self._llm_client
                else None
            )
            logger.info("LLM config (unitForms): %s", format_llm_log(llm_cfg, None, supports_fn))
            user_parts = [
                part.strip()
                for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
                if part and part.strip()
            ]
            user_prompt = "\n\n".join(user_parts).strip() or replacements["unit_lines"]
            system_prompt = prompt_cfg.get("system") or ""
            log_prompt_messages(
                "unitForms",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            self._maybe_confirm(confirm, f"LLM Einheitenformen – {', '.join(batch)}")
            self._debug_write(
                debug,
                "units_llm_request",
                {
                    "batch": batch,
                    "systemPrompt": system_prompt,
                    "userPrompt": user_prompt,
                },
            )
            llm_cfg = resolve_llm_config("unitForms")
            response = self._llm_client.run_json(system_prompt, user_prompt, llm_config=llm_cfg)
            self._debug_write(
                debug,
                "units_llm_response",
                {
                    "batch": batch,
                    "response": response,
                },
            )
        except UserAbort:
            raise
        except Exception as exc:
            logger.warning("LLM konnte Einheiten nicht bestimmen (%s): %s", ", ".join(batch), exc)
            self._debug_write(
                debug,
                "units_llm_response_error",
                {
                    "batch": batch,
                    "error": str(exc),
                },
            )
            return {}

        requested = {self._normalize(name): name for name in batch if self._normalize(name)}
        return self._parse_unit_form_response(response, requested, debug=debug)

    def _parse_form_response(
        self,
        payload: Mapping[str, Any],
        requested: Mapping[str, str],
        categories: Iterable[Dict[str, str]],
        *,
        debug: Optional[Any] = None,
    ) -> Dict[str, FoodForms]:
        category_by_id: Dict[str, str] = {}
        category_by_name: Dict[str, str] = {}
        for item in categories:
            cat_id = str(item.get("id") or "").strip()
            cat_name = str(item.get("name") or "").strip()
            if not cat_id or not cat_name:
                continue
            category_by_id[cat_id] = cat_name
            category_by_name[self._normalize(cat_name)] = cat_id

        items = payload.get("ingredients")
        if not isinstance(items, list):
            logger.debug("LLM-Formantwort ohne ingredients-Feld: %s", payload)
            self._debug_write(
                debug,
                "foods_llm_response_invalid",
                {
                    "payload": payload,
                    "reason": "missing_ingredients_field",
                },
            )
            return {}

        results: Dict[str, FoodForms] = {}
        for entry in items:
            if not isinstance(entry, Mapping):
                continue
            raw_input = str(entry.get("input") or "").strip()
            normalized_input = self._normalize(raw_input)
            if normalized_input not in requested:
                continue

            singular = str(entry.get("nameSingular") or "").strip()
            plural = str(entry.get("namePlural") or "").strip()
            if not singular:
                continue

            countable_field = entry.get("countable")
            countable = bool(countable_field) if isinstance(countable_field, bool) else None
            if not plural:
                plural = singular
            if countable is None:
                countable = self._normalize(singular) != self._normalize(plural)
            if not countable:
                plural = singular

            alias_candidates = entry.get("aliasesStrict") or []
            aliases: List[str] = []
            if isinstance(alias_candidates, list):
                for alias in alias_candidates:
                    sanitized = self._sanitize_alias_value(alias)
                    if sanitized:
                        aliases.append(sanitized)

            category_id_raw = entry.get("categoryId")
            category_name_raw = entry.get("categoryName")
            label_id: Optional[str] = None
            label_name: Optional[str] = None

            if isinstance(category_id_raw, str) and category_id_raw.strip():
                candidate_id = category_id_raw.strip()
                if candidate_id in category_by_id:
                    label_id = candidate_id
                    label_name = category_by_id[candidate_id]
                else:
                    logger.debug("LLM lieferte unbekannte Kategorie-ID %s", candidate_id)
                    self._debug_write(
                        debug,
                        "foods_llm_response_invalid_category",
                        {"providedId": candidate_id},
                    )

            if not label_id and isinstance(category_name_raw, str) and category_name_raw.strip():
                normalized_cat = self._normalize(category_name_raw)
                candidate_id = category_by_name.get(normalized_cat)
                if candidate_id:
                    label_id = candidate_id
                    label_name = category_by_id[candidate_id]
                elif category_name_raw.strip():
                    self._debug_write(
                        debug,
                        "foods_llm_response_invalid_category",
                        {"providedName": category_name_raw},
                    )

            if label_id and not label_name:
                label_name = category_by_id.get(label_id)

            results[normalized_input] = FoodForms(
                singular=singular,
                plural=plural,
                countable=countable,
                aliases=aliases[:8],
                label_id=label_id,
                label_name=label_name,
            )
        missing = set(requested) - set(results)
        if missing:
            logger.debug("LLM lieferte keine Formen für: %s", ", ".join(sorted(requested[key] for key in missing)))
            self._debug_write(
                debug,
                "foods_llm_response_missing",
                {
                    "missing": [requested[key] for key in missing],
                },
            )
        if results:
            self._debug_write(
                debug,
                "foods_llm_response_parsed",
                {
                    "results": {
                        requested.get(normalized_key, normalized_key): self._forms_to_dict(forms)
                        for normalized_key, forms in results.items()
                    },
                },
                )
        return results

    def _merge_aliases(
        self,
        forms_aliases: Iterable[str],
        extra_aliases: Optional[Iterable[str]],
        *,
        singular: str,
        plural: str,
    ) -> List[str]:
        merged: List[str] = []
        seen: set[str] = set()
        forbidden = {self._normalize(singular), self._normalize(plural)}

        def add(alias_value: Optional[str]) -> None:
            if not alias_value:
                return
            normalized = self._normalize(alias_value)
            if not normalized or normalized in seen or normalized in forbidden:
                return
            seen.add(normalized)
            merged.append(alias_value)

        for alias in extra_aliases or []:
            add(self._sanitize_alias_value(alias))

        for alias in forms_aliases:
            add(self._sanitize_alias_value(alias))

        if len(merged) > 8:
            merged = merged[:8]
        return merged

    def _extract_alias_strings(self, food: Mapping[str, Any]) -> List[str]:
        aliases_raw = food.get("aliases") or []
        collected: List[str] = []
        for item in aliases_raw:
            value = None
            if isinstance(item, Mapping):
                value = item.get("name")
            elif isinstance(item, str):
                value = item
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            if stripped:
                collected.append(stripped)
        return collected

    def _sanitize_alias_value(self, alias: Any) -> Optional[str]:
        if isinstance(alias, Mapping):
            alias = alias.get("name")
        text = str(alias or "").strip()
        if not text:
            return None
        sanitized = re.sub(r"\s+", " ", text)
        return sanitized or None

    def _forms_to_dict(self, forms: FoodForms) -> Dict[str, Any]:
        return {
            "singular": forms.singular,
            "plural": forms.plural,
            "countable": forms.countable,
            "aliases": list(forms.aliases),
            "labelId": forms.label_id,
            "labelName": forms.label_name,
        }

    def _parse_unit_form_response(
        self,
        payload: Mapping[str, Any],
        requested: Mapping[str, str],
        *,
        debug: Optional[Any] = None,
    ) -> Dict[str, UnitForms]:
        items = payload.get("units")
        if not isinstance(items, list):
            self._debug_write(
                debug,
                "units_llm_response_invalid",
                {"payload": payload},
            )
            return {}

        results: Dict[str, UnitForms] = {}
        for entry in items:
            if not isinstance(entry, Mapping):
                continue
            raw_input = str(entry.get("input") or "").strip()
            normalized_input = self._normalize(raw_input)
            if normalized_input not in requested:
                continue

            name = str(entry.get("name") or "").strip()
            if not name:
                continue

            plural_name = str(entry.get("pluralName") or "").strip() or None
            abbreviation = str(entry.get("abbreviation") or "").strip() or None
            plural_abbreviation = str(entry.get("pluralAbbreviation") or "").strip() or None
            use_abbreviation = bool(entry.get("useAbbreviation")) and bool(abbreviation)

            plural_abbreviation = self._clean_plural_abbreviation(
                singular=name,
                plural=plural_name,
                abbreviation=abbreviation,
                plural_abbreviation=plural_abbreviation,
            )

            results[normalized_input] = UnitForms(
                name=self._capitalize_first(name),
                plural_name=plural_name,
                abbreviation=abbreviation,
                plural_abbreviation=plural_abbreviation,
                use_abbreviation=use_abbreviation,
            )

        missing = set(requested) - set(results)
        if missing:
            self._debug_write(
                debug,
                "units_llm_response_missing",
                {"missing": [requested[key] for key in missing]},
            )
        return results

    def _debug_write(self, recorder: Optional[Any], label: str, data: Mapping[str, Any]) -> None:
        if not recorder:
            return
        try:
            if hasattr(recorder, "write"):
                recorder.write(label, data)
            elif hasattr(recorder, "write_json"):
                recorder.write_json(label, data)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - debug helper
            logger.debug("Konnte Debug-Datei nicht schreiben (%s): %s", label, exc)

    def _maybe_confirm(self, confirm: Optional[Callable[[str], None]], label: str) -> None:
        if confirm:
            confirm(label)

    @staticmethod
    def _clean_plural_abbreviation(
        singular: str,
        plural: Optional[str],
        abbreviation: Optional[str],
        plural_abbreviation: Optional[str],
    ) -> Optional[str]:
        if not plural_abbreviation:
            return None
        normalized_plural_abbr = re.sub(r"\s+", " ", plural_abbreviation).strip()
        if not normalized_plural_abbr:
            return None

        def _normalize(value: Optional[str]) -> str:
            return re.sub(r"\s+", " ", (value or "").strip()).lower()

        singular_norm = _normalize(singular)
        plural_norm = _normalize(plural)
        plural_abbr_norm = _normalize(plural_abbreviation)
        abbreviation_norm = _normalize(abbreviation)

        if plural_abbr_norm in {"-", "–", "—", "n/a", "none"}:
            return None
        if plural_abbr_norm in {singular_norm, plural_norm}:
            return None
        if abbreviation and plural_abbr_norm == abbreviation_norm:
            return None
        return normalized_plural_abbr

    @staticmethod
    def _response_debug_payload(response: httpx.Response) -> Dict[str, Any]:
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        return {
            "status": response.status_code,
            "body": body,
        }

    def _capitalize_first(self, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        return value[0].upper() + value[1:]

    def _normalize(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value or "").strip().lower()
        return normalized

    def _normalize_strict(self, value: str) -> str:
        normalized = self._normalize(value)
        stripped = re.sub(r"[^\w\säöüß-]", "", normalized)
        return re.sub(r"\s+", " ", stripped).strip()

    def _score(self, left: str, right: str) -> int:
        if fuzz:
            return int(fuzz.ratio(left, right))
        left_norm = self._normalize(left)
        right_norm = self._normalize(right)
        if left_norm == right_norm:
            return 100
        if self._normalize_strict(left) == self._normalize_strict(right):
            return 100
        return 0

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
