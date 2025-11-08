"""Match recipe ingredients against existing Mealie foods."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

from ..context import IngredientRef, PipelineContext
from ...llm_parser import OpenAiClient
from ...services.ingredients import IngredientService

logger = logging.getLogger("Food Checker")

STATUS_FOUND_WORD = "found_word"
STATUS_FOUND_FUZZY = "found_fuzzy"
STATUS_FOUND_AI = "found_ai"
STATUS_NEW = "new"
STATUS_NONE = "none"

_SYSTEM_PROMPT = ("""
    Du vergleichst Zutaten aus einem Rezept mit den vorhandenen Lebensmitteln in Mealie.
    Wähle nur dann ein Lebensmittel, wenn es inhaltlich exakt passt – nicht nur teilweise.
    Ignoriere Farb-, Herkunfts- oder Sortenunterschiede nicht („rote Zwiebeln“ ist nicht dasselbe wie „Zwiebeln“, „grüner Pfeffer“ ist nicht dasselbe wie „Pfeffer“).
    Wähle keine allgemeinere Kategorie, wenn das Rezept spezifischer ist.
    Wähle keine eng verwandten, aber unterschiedlichen Zutaten (z. B. „Butter“ ≠ „Margarine“).
    Wähle nur ein Lebensmittel, wenn du dir sicher bist, dass es exakt dasselbe meint.
    Wenn du unsicher bist oder mehrere ähnliche Treffer möglich sind, gib keinen Treffer zurück.
    '{"match": <ID oder null>, "reason": "..."}."'
""")


@dataclass
class _FoodCandidate:
    id: str
    name: str
    plural: str
    aliases: List[str]

    @classmethod
    def from_raw(cls, raw: Dict[str, object]) -> "_FoodCandidate":
        return cls(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            plural=str(raw.get("pluralName") or raw.get("name") or ""),
            aliases=[str(alias) for alias in (raw.get("aliases") or [])],
        )


class FoodCheckerModule:
    """Verify ingredient foods and prepare mappings to Mealie IDs."""

    name = "Food Checker"

    def __init__(
        self,
        ingredient_service: Optional[IngredientService],
        *,
        llm_client: Optional[OpenAiClient] = None,
    ) -> None:
        self._service = ingredient_service
        self._llm_client = llm_client
        self._foods: List[_FoodCandidate] = []

    def run(self, context: PipelineContext) -> None:
        ingredient_refs = list(context.iter_ingredients())
        total = len(ingredient_refs)
        if total == 0:
            logger.info("No ingredients found for this recipe, so we skip the food checker")
            return

        ingredient_names = [ref.ingredient.name for ref in ingredient_refs if ref.ingredient.name]
        logger.info(
            "Trying to match %s ingredient%s to existing foods in Mealie %s",
            total,
            "s" if total != 1 else "",
            self._format_list(ingredient_names),
        )

        reference = self._load_reference_data(context)
        self._write_cache(reference, context)
        foods_by_id = self._foods_dict()

        matches: Dict[str, str] = {}
        match_details: Dict[str, Dict[str, object]] = {}
        exact_matches: List[str] = []
        fuzzy_matches: List[tuple[str, str]] = []
        ai_matches: List[str] = []
        pending_ai_refs: List[IngredientRef] = []

        for ref in ingredient_refs:
            ingredient = ref.ingredient
            if ingredient.mealie_food_id:
                matches[ref.key] = ingredient.mealie_food_id
                match_details[ref.key] = {"strategy": "preassigned"}
                exact_matches.append(ingredient.name)
                continue

            candidate_id, strategy, matched_label = self._stage_one_match(ingredient.name)
            if candidate_id:
                matches[ref.key] = candidate_id
                match_details[ref.key] = {"strategy": strategy}
                if strategy == "exact":
                    exact_matches.append(ingredient.name)
                else:
                    candidate = foods_by_id.get(candidate_id)
                    display = matched_label or (candidate.name if candidate else candidate_id)
                    fuzzy_matches.append((ingredient.name, display))
                continue

            pending_ai_refs.append(ref)

        missing: List[IngredientRef] = []
        unresolved_names: List[str] = []

        if exact_matches:
            logger.info(
                "Matched %s ingredient%s exact by words: %s",
                len(exact_matches),
                "" if len(exact_matches) == 1 else "s",
                self._format_list(exact_matches),
            )
        if fuzzy_matches:
            logger.info(
                "Matched %s ingredient%s with Fuzzy-Search: %s",
                len(fuzzy_matches),
                "" if len(fuzzy_matches) == 1 else "s",
                self._format_fuzzy_pairs(fuzzy_matches),
            )

        if pending_ai_refs:
            pending_names = [ref.ingredient.name for ref in pending_ai_refs if ref.ingredient.name]
            logger.info(
                "Try matching rest of the ingredients %s with AI",
                self._format_list(pending_names),
            )

        for ref in pending_ai_refs:
            ingredient = ref.ingredient
            logger.info(
                "Ask AI to find [%s] in existing foods in Mealie",
                ingredient.name,
            )
            candidate_id, candidate_name = self._stage_two_with_llm(ingredient.name)
            if candidate_id:
                matches[ref.key] = candidate_id
                match_details[ref.key] = {"strategy": "ai"}
                ai_matches.append(ingredient.name)
                logger.info(
                    "AI suggests [%s] from existing foods in Mealie",
                    candidate_name or candidate_id,
                )
            else:
                logger.info(
                    "AI could not find a matching ingredient for [%s] in existing foods in Mealie",
                    ingredient.name,
                )
                missing.append(ref)
                unresolved_names.append(ingredient.name)

        context.food_matches = matches
        context.missing_food_refs = missing
        self._update_recipe_matches(context, ingredient_refs, matches, match_details, missing)

        logger.info(
            "Matched %s ingredient%s so far; %s still need attention",
            len(matches),
            "s" if len(matches) != 1 else "",
            len(missing),
        )
        self._log_stats(
            exact_matches,
            fuzzy_matches,
            ai_matches,
            ingredient_refs,
            missing,
            include_stage_one=False,
        )

        suggestions: Dict[str, Dict[str, object]] = {}
        if unresolved_names and self._service:
            logger.info(
                "Will ask AI for naming suggestions for missing ingredients",
            )
            for name in unresolved_names:
                logger.info(
                    "Ask AI for singular, plural, aliases and mapping to existing food category for [%s]",
                    name,
                )
            try:
                self._service.prepare_food_forms(
                    unresolved_names,
                    debug=context.pipeline_recorder,
                )
            except Exception as exc:  # pragma: no cover - external dependency
                logger.debug("Could not prepare food-form suggestions: %s", exc)
            try:
                suggestions = self._service.food_form_suggestions(
                    unresolved_names,
                    debug=context.pipeline_recorder,
                )
            except Exception as exc:  # pragma: no cover - external dependency
                logger.debug("Could not retrieve food-form suggestions: %s", exc)
            for name in unresolved_names:
                suggestion = suggestions.get(name)
                if suggestion:
                    logger.info(
                        "AI returns this suggestion for [%s]: singular [%s], plural [%s], aliases %s, category [%s]",
                        name,
                        suggestion.get("nameSingular") or "-",
                        suggestion.get("namePlural") or "-",
                        self._format_list(suggestion.get("aliases") or []),
                        suggestion.get("categoryName") or "-",
                    )
                else:
                    logger.info(
                        "AI could not generate a suggestion for [%s]",
                        name,
                    )

        categories = reference.get("categories", [])
        self._write_review(
            context,
            ingredient_refs,
            matches,
            match_details,
            missing,
            suggestions,
            categories,
        )

    # ------------------------------------------------------------------
    # Reference data handling
    # ------------------------------------------------------------------
    def _load_reference_data(self, context: PipelineContext) -> Dict[str, object]:
        foods: List[_FoodCandidate] = []
        categories: List[Dict[str, object]] = []

        if self._service:
            foods = [
                _FoodCandidate.from_raw(item)
                for item in self._service.list_foods()
                if item.get("id")
            ]
            categories = list(self._service.list_food_categories())

        if not foods:
            cache_path = context.cache_paths.foods_cache
            if cache_path.exists():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    logger.debug("Ignoring MealieFoodsCache.json because it is not valid JSON")
                else:
                    foods = [
                        _FoodCandidate.from_raw(item)
                        for item in cached.get("foods", [])
                        if item.get("id")
                    ]

        if not categories:
            categories_path = context.cache_paths.food_categories_cache
            if categories_path.exists():
                try:
                    cached_categories = json.loads(categories_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    logger.debug("Ignoring MealieFoodCategoriesCache.json because it is not valid JSON")
                else:
                    categories = list(cached_categories.get("categories", []))

        self._foods = foods
        return {
            "foods": [
                {
                    "id": item.id,
                    "name": item.name,
                    "pluralName": item.plural,
                    "aliases": item.aliases,
                }
                for item in foods
            ],
            "categories": categories,
        }

    def _write_cache(self, snapshot: Dict[str, object], context: PipelineContext) -> None:
        timestamp = datetime.utcnow().isoformat()
        foods_payload = {
            "updated_at": timestamp,
            "foods": snapshot.get("foods", []),
        }
        context.cache_paths.foods_cache.write_text(
            json.dumps(foods_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        categories_payload = {
            "updated_at": timestamp,
            "categories": snapshot.get("categories", []),
        }
        context.cache_paths.food_categories_cache.write_text(
            json.dumps(categories_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------
    def _stage_one_match(self, query: str) -> tuple[Optional[str], str, Optional[str]]:
        if not query:
            return None, "exact", None
        exact_id, exact_label = self._exact_match(query)
        if exact_id:
            return exact_id, "exact", exact_label
        fuzzy_id, fuzzy_label = self._fuzzy_match_offline(query)
        if fuzzy_id:
            return fuzzy_id, "fuzzy", fuzzy_label
        return None, "exact", None

    def _exact_match(self, query: str) -> tuple[Optional[str], Optional[str]]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return None, None
        for candidate in self._foods:
            if candidate.name.strip().lower() == normalized_query:
                return candidate.id, candidate.name
            if candidate.plural.strip().lower() == normalized_query:
                return candidate.id, candidate.plural
            for alias in candidate.aliases:
                if alias.strip().lower() == normalized_query:
                    return candidate.id, alias
        return None, None

    def _fuzzy_match_offline(self, query: str) -> tuple[Optional[str], Optional[str]]:
        if not self._foods:
            return None, None
        best_id: Optional[str] = None
        best_label: Optional[str] = None
        best_score = 0.0
        normalized_query = query.strip().lower()
        for candidate in self._foods:
            for option in self._candidate_names(candidate):
                normalized_option = option.lower()
                if normalized_option == normalized_query:
                    return candidate.id, option
                score = SequenceMatcher(None, normalized_query, normalized_option).ratio()
                if score > best_score:
                    best_score = score
                    best_id = candidate.id
                    best_label = option
        if best_score >= 0.9:
            return best_id, best_label
        return None, None

    def _stage_two_with_llm(self, query: str) -> tuple[Optional[str], Optional[str]]:
        if not self._llm_client or not self._foods:
            return None, None

        candidates = self._top_candidates(query, limit=10)
        if not candidates:
            return None, None

        candidate_lines = []
        for candidate in candidates:
            alias_part = ", ".join(candidate.aliases) if candidate.aliases else "-"
            candidate_lines.append(
                f"- {candidate.id}: {candidate.name} (Plural: {candidate.plural}; Aliases: {alias_part})"
            )
        user_prompt = (
            f"Ingredient: {query}\n"
            "Candidates:\n"
            + "\n".join(candidate_lines)
            + '\nResponse format: {"match": <ID or null>, "reason": string}'
        )

        try:
            response = self._llm_client.run_text(_SYSTEM_PROMPT, user_prompt)
        except Exception as exc:  # pragma: no cover - external dependency
            logger.debug("Assistant lookup failed: %s", exc)
            return None, None

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.debug("Assistant response was not valid JSON: %s", response[:120])
            return None, None

        match_id = data.get("match")
        if not isinstance(match_id, str):
            logger.debug('The assistant could not find a confident match for "%s"', query)
            return None, None

        known_ids = {candidate.id for candidate in candidates}
        if match_id not in known_ids:
            logger.debug("The assistant suggested an unknown food id %s", match_id)
            return None, None

        food = self._foods_dict().get(match_id)
        return match_id, (food.name if food else None)

    # ------------------------------------------------------------------
    # Review and reporting
    # ------------------------------------------------------------------
    def _log_stats(
        self,
        exact_matches: List[str],
        fuzzy_matches: List[tuple[str, str]],
        ai_matches: List[str],
        ingredient_refs: List[IngredientRef],
        missing: List[IngredientRef],
        *,
        include_stage_one: bool = False,
    ) -> None:
        total = len(ingredient_refs)
        if total == 0:
            return

        if include_stage_one and exact_matches:
            logger.info(
                "Matched %s ingredient%s exact by words: %s",
                len(exact_matches),
                "" if len(exact_matches) == 1 else "s",
                self._format_list(exact_matches),
            )
        if include_stage_one and fuzzy_matches:
            logger.info(
                "Matched %s ingredient%s with Fuzzy-Search: %s",
                len(fuzzy_matches),
                "" if len(fuzzy_matches) == 1 else "s",
                self._format_fuzzy_pairs(fuzzy_matches),
            )
        if ai_matches:
            logger.info(
                "Matched %s ingredient%s with AI: %s",
                len(ai_matches),
                "" if len(ai_matches) == 1 else "s",
                self._format_list(ai_matches),
            )
        if missing:
            missing_names = [ref.ingredient.name for ref in missing if ref.ingredient.name]
            logger.info(
                "%s ingredient%s need to be created in Mealie: %s",
                len(missing_names),
                "" if len(missing_names) == 1 else "s",
                self._format_list(missing_names),
            )
        else:
            logger.info("Every ingredient now has a Mealie food match")

    def _write_review(
        self,
        context: PipelineContext,
        ingredient_refs: List[IngredientRef],
        matches: Dict[str, str],
        match_details: Dict[str, Dict[str, object]],
        missing: List[IngredientRef],
        suggestions: Dict[str, Dict[str, object]],
        categories: List[Dict[str, object]],
    ) -> None:
        recorder = context.pipeline_recorder
        if not recorder:
            logger.debug("No pipeline recorder available, so no foods review file was created")
            return

        recipe = context.ensure_recipe()
        foods_by_id = {item.id: item for item in self._foods}
        missing_keys = {ref.key for ref in missing}
        items: List[Dict[str, object]] = []

        for ref in ingredient_refs:
            section_name = ""
            if 0 <= ref.section_index < len(recipe.ingredients):
                section = recipe.ingredients[ref.section_index]
                section_name = section.name or f"Section {ref.section_index + 1}"

            ingredient = ref.ingredient
            key = ref.key
            matched_id = matches.get(key)
            matched_food = foods_by_id.get(matched_id) if matched_id else None
            suggestion = suggestions.get(ingredient.name)
            create_defaults = {
                "nameSingular": None,
                "namePlural": None,
                "aliases": [],
                "categoryId": None,
                "categoryName": None,
                "description": None,
            }
            if suggestion:
                create_defaults.update(
                    {
                        "nameSingular": suggestion.get("nameSingular"),
                        "namePlural": suggestion.get("namePlural"),
                        "aliases": suggestion.get("aliases") or [],
                        "categoryId": suggestion.get("categoryId"),
                        "categoryName": suggestion.get("categoryName"),
                    }
                )
            candidates = [
                {
                    "id": candidate.id,
                    "name": candidate.name,
                    "pluralName": candidate.plural,
                }
                for candidate in self._top_candidates(ingredient.name, limit=5)
            ]

            items.append(
                {
                    "key": key,
                    "sectionIndex": ref.section_index,
                    "sectionName": section_name,
                    "ingredientIndex": ref.ingredient_index,
                    "ingredient": {
                        "name": ingredient.name,
                        "quantity": ingredient.quantity,
                        "unit": ingredient.unit,
                        "note": ingredient.note,
                    },
                    "currentMatch": (
                        {
                            "foodId": matched_id,
                            "name": matched_food.name if matched_food else None,
                            "strategy": match_details.get(key, {}).get("strategy"),
                        }
                        if matched_id
                        else None
                    ),
                    "status": "missing" if key in missing_keys else "matched",
                    "candidates": candidates,
                    "suggestion": suggestion,
                    "userDecision": {
                        "action": "auto",
                        "useFoodId": None,
                        "create": create_defaults,
                        "notes": "",
                    },
                }
            )

        payload = {
            "generatedAt": datetime.utcnow().isoformat(),
            "summary": {
                "totalIngredients": len(ingredient_refs),
                "autoMatched": len(ingredient_refs) - len(missing),
                "missing": len(missing),
            },
            "instructions": (
                "Adjust 'userDecision' for each ingredient if you want to override the automatic choice. "
                "action = 'auto' keeps current behaviour, 'use_existing' expects useFoodId, "
                "'create' expects details under create, 'skip' ignores the ingredient."
            ),
            "availableCategories": categories,
            "ingredients": items,
        }

        review_path = recorder.write_json("FoodsReview", payload)
        context.food_review_path = review_path
        context.food_decisions = {}
        logger.info("Saved the foods review to %s", review_path)

    def _update_recipe_matches(
        self,
        context: PipelineContext,
        ingredient_refs: List[IngredientRef],
        matches: Dict[str, str],
        match_details: Dict[str, Dict[str, object]],
        missing: List[IngredientRef],
    ) -> None:
        recipe = context.ensure_recipe()
        missing_keys = {ref.key for ref in missing}
        for ref in ingredient_refs:
            ingredient = ref.ingredient
            match_id = matches.get(ref.key)
            ingredient.mealie_food_id = match_id
            if match_id:
                strategy = (match_details.get(ref.key) or {}).get("strategy")
                ingredient.food_badge_id = self._badge_for_strategy(strategy)
            elif ref.key in missing_keys:
                ingredient.food_badge_id = STATUS_NEW
            else:
                ingredient.food_badge_id = STATUS_NONE
        context.update_recipe_file()

    @staticmethod
    def _badge_for_strategy(strategy: Optional[object]) -> str:
        if strategy == "exact" or strategy == "preassigned":
            return STATUS_FOUND_WORD
        if strategy == "fuzzy":
            return STATUS_FOUND_FUZZY
        if strategy == "ai":
            return STATUS_FOUND_AI
        return STATUS_FOUND_WORD

    # ------------------------------------------------------------------
    # Candidate helpers
    # ------------------------------------------------------------------
    def _top_candidates(self, query: str, *, limit: int) -> List[_FoodCandidate]:
        scored: List[tuple[float, _FoodCandidate]] = []
        normalized_query = query.strip().lower()
        for candidate in self._foods:
            best_score = 0.0
            for option in self._candidate_names(candidate):
                score = SequenceMatcher(None, normalized_query, option.lower()).ratio()
                if score > best_score:
                    best_score = score
            if best_score > 0:
                scored.append((best_score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)

        unique: List[_FoodCandidate] = []
        seen_ids: set[str] = set()
        for _, candidate in scored:
            if candidate.id in seen_ids:
                continue
            unique.append(candidate)
            seen_ids.add(candidate.id)
            if len(unique) >= limit:
                break
        return unique

    def _candidate_names(self, candidate: _FoodCandidate) -> Iterable[str]:
        yield candidate.name
        if candidate.plural:
            yield candidate.plural
        for alias in candidate.aliases:
            yield alias

    def _foods_dict(self) -> Dict[str, _FoodCandidate]:
        return {item.id: item for item in self._foods}

    @staticmethod
    def _format_list(values: Iterable[str]) -> str:
        cleaned = [str(value) for value in values if value]
        if not cleaned:
            return "[]"
        return "[" + ", ".join(cleaned) + "]"

    @staticmethod
    def _format_fuzzy_pairs(pairs: Iterable[tuple[str, str]]) -> str:
        entries = [
            f"[{source}] > [{target}]"
            for source, target in pairs
            if source and target
        ]
        if not entries:
            return "[]"
        return ", ".join(entries)
