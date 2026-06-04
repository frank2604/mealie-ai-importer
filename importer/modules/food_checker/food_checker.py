"""Match recipe ingredients against existing Mealie foods."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from ..context import IngredientRef, PipelineContext
from ...llm_client import LLMClient
from ...config import LlmConfig
from ...prompt_store import resolve_prompt, resolve_llm_config
from ...prompt_logging import log_prompt_messages
from ...llm_utils import format_llm_log
from ...services.ingredients import IngredientService
from ...services.embeddings import FoodEmbeddingIndex
from ...services.text_norm import normalize_de

logger = logging.getLogger("Food Checker")

STATUS_FOUND_WORD = "found_word"
STATUS_FOUND_FUZZY = "found_fuzzy"
STATUS_FOUND_AI = "found_ai"
STATUS_NEW = "new"
STATUS_NONE = "none"

# How many semantic candidates to hand the LLM per ingredient. A handful keeps
# the prompt small; 8 gives the LLM enough recall headroom on harder synonyms.
SHORTLIST_K = 8
# When the embedding index is unavailable we fall back to sending the whole food
# list to the LLM, but cap it to keep the prompt bounded.
FULL_LIST_CAP = 200

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
    internal_id: str
    name: str
    plural: str
    aliases: List[str]

    @classmethod
    def from_raw(cls, raw: Dict[str, object]) -> "_FoodCandidate":
        return cls(
            id=str(raw.get("id") or ""),
            internal_id=str(raw.get("internalFoodId") or ""),
            name=str(raw.get("name") or ""),
            plural=str(raw.get("pluralName") or raw.get("name") or ""),
            aliases=[
                alias["name"] if isinstance(alias, dict) else str(alias)
                for alias in (raw.get("aliases") or [])
                if (alias["name"] if isinstance(alias, dict) else str(alias)).strip()
            ],
        )


class FoodCheckerModule:
    """Verify ingredient foods and prepare mappings to Mealie IDs."""

    name = "Food Checker"

    def __init__(
        self,
        ingredient_service: Optional[IngredientService],
        *,
        llm_client: Optional[LLMClient] = None,
        llm_config: Optional["LlmConfig"] = None,
        locale: str = "de",
    ) -> None:
        self._service = ingredient_service
        self._llm_client = llm_client
        self._foods: List[_FoodCandidate] = []
        self._locale = locale or "de"
        self._llm_config = llm_config
        self._internal_map: Dict[str, str] = {}  # internalFoodId -> mealieFoodId
        self._normalized_lookup: Dict[str, str] = {}  # normalized name/plural/alias -> mealieFoodId
        self._index: Optional[FoodEmbeddingIndex] = None

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
        self._normalized_lookup = self._build_normalized_lookup()
        self._index = self._build_index(context)

        matches: Dict[str, str] = {}
        match_details: Dict[str, Dict[str, object]] = {}
        exact_matches: List[str] = []
        fuzzy_matches: List[tuple[str, str]] = []
        ai_matches: List[str] = []
        pending_ai_refs: List[IngredientRef] = []
        unresolved_after_exact: List[IngredientRef] = []

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
            unresolved_after_exact.append(ref)

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
                "Auto-accepted %s ingredient%s by semantic similarity: %s",
                len(fuzzy_matches),
                "" if len(fuzzy_matches) == 1 else "s",
                self._format_fuzzy_pairs(fuzzy_matches),
            )

        if pending_ai_refs:
            pending_names = [ref.ingredient.name for ref in pending_ai_refs if ref.ingredient.name]
            search_mode = "semantic shortlist + AI" if (self._index and self._index.available) else "AI"
            logger.info(
                "Try matching rest of the ingredients %s with %s",
                self._format_list(pending_names),
                search_mode,
            )

        if pending_ai_refs:
            ai_map = self._stage_two_batch_with_llm(pending_ai_refs)
            for ref in pending_ai_refs:
                ingredient = ref.ingredient
                candidate_id = ai_map.get(ref.key)
                if candidate_id:
                    matches[ref.key] = candidate_id
                    match_details[ref.key] = {"strategy": "ai"}
                    ai_matches.append(ingredient.name)
                    logger.info("AI suggests [%s] from existing foods in Mealie", candidate_id)
                else:
                    logger.info(
                        "AI could not find a matching ingredient for [%s] in existing foods in Mealie",
                        ingredient.name,
                    )
                    missing.append(ref)
                    unresolved_names.append(ingredient.name)

        context.food_matches = matches
        context.missing_food_refs = missing
        new_ids = {ref.key: self._build_new_id("food", ref) for ref in missing}
        self._update_recipe_matches(context, ingredient_refs, matches, match_details, missing, new_ids)

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

        self._write_review(
            context,
            ingredient_refs,
            matches,
            match_details,
            missing,
            suggestions,
            new_ids,
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

        foods = self._assign_internal_ids(foods)
        self._foods = foods
        self._internal_map = {item.internal_id: item.id for item in foods if item.internal_id}
        return {
            "foods": [
                {
                    "id": item.id,
                    "internalFoodId": item.internal_id,
                    "name": item.name,
                    "pluralName": item.plural,
                    "aliases": item.aliases,
                }
                for item in foods
            ],
            "categories": categories,
        }

    def _assign_internal_ids(self, foods: List[_FoodCandidate]) -> List[_FoodCandidate]:
        """Ensure every candidate has a stable short internalFoodId."""
        result: List[_FoodCandidate] = []
        # Start counter after the highest existing numeric internal_id
        existing_numbers: List[int] = []
        for item in foods:
            try:
                existing_numbers.append(int(str(item.internal_id).strip()))
            except (TypeError, ValueError):
                continue
        counter = (max(existing_numbers) + 1) if existing_numbers else 1
        seen: set[str] = set()
        for item in foods:
            internal = item.internal_id.strip()
            if not internal or internal in seen:
                internal = str(counter)
                counter += 1
            seen.add(internal)
            item.internal_id = internal
            result.append(item)
        # Falls Cache geladen, aber neue Elemente ohne ID hinzukommen: weiterzählen
        return result

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
    def _build_normalized_lookup(self) -> Dict[str, str]:
        """Map every normalized food name/plural/alias to its Mealie id."""
        lookup: Dict[str, str] = {}
        for candidate in self._foods:
            for label in self._candidate_names(candidate):
                key = normalize_de(label)
                if key and key not in lookup:
                    lookup[key] = candidate.id
        return lookup

    def _build_index(self, context: PipelineContext) -> Optional[FoodEmbeddingIndex]:
        use_embeddings = True
        try:
            use_embeddings = bool(context.config.ingredients.use_embeddings)
        except AttributeError:  # pragma: no cover - defensive
            pass
        cache_path = context.cache_paths.root / "MealieFoodsEmbeddings.json"
        index = FoodEmbeddingIndex(cache_path, enabled=use_embeddings)
        if index.available:
            try:
                index.build_or_update(self._foods)
                logger.info("Semantic food index ready (%s foods)", len(self._foods))
            except Exception as exc:  # pragma: no cover - external dependency
                logger.warning("Could not build the semantic food index: %s", exc)
        else:
            logger.info("Semantic food index disabled; matching falls back to the LLM over the food list")
        return index

    def _stage_one_match(self, query: str) -> tuple[Optional[str], str, Optional[str]]:
        """Deterministic normalized exact match (name/plural/alias)."""
        if not query:
            return None, "exact", None
        key = normalize_de(query)
        if not key:
            return None, "exact", None
        food_id = self._normalized_lookup.get(key)
        if food_id:
            candidate = self._foods_dict().get(food_id)
            return food_id, "exact", (candidate.name if candidate else None)
        return None, "exact", None

    def _shortlist_candidates(self, ref: IngredientRef) -> List[_FoodCandidate]:
        """Semantic top-K candidates, or the (capped) full list as a fallback."""
        foods_by_id = self._foods_dict()
        if self._index is not None and self._index.available:
            hits = self._index.shortlist(ref.ingredient.name or "", k=SHORTLIST_K)
            shortlisted: List[_FoodCandidate] = []
            for food_id, _score in hits:
                candidate = foods_by_id.get(food_id)
                if candidate is not None:
                    shortlisted.append(candidate)
            return shortlisted
        return list(self._foods)[:FULL_LIST_CAP]

    @staticmethod
    def _candidate_detail_line(candidate: _FoodCandidate) -> str:
        extras: List[str] = []
        if candidate.plural and candidate.plural != candidate.name:
            extras.append(f"Plural: {candidate.plural}")
        if candidate.aliases:
            extras.append("Aliase: " + ", ".join(candidate.aliases))
        suffix = f" ({'; '.join(extras)})" if extras else ""
        return f"- {candidate.internal_id}: {candidate.name}{suffix}"

    def _stage_two_batch_with_llm(self, refs: List[IngredientRef]) -> Dict[str, Optional[str]]:
        """Ask the LLM to adjudicate the remaining ingredients.

        Each ingredient is paired with a small semantic shortlist of candidate
        foods (or, when embeddings are unavailable, the capped full list). The
        LLM picks the matching candidate id or returns null. Returns a mapping
        ref.key -> mealie_food_id (or None).
        """
        result: Dict[str, Optional[str]] = {ref.key: None for ref in refs}
        if not self._llm_client or not self._foods:
            return result

        per_ingredient = self._index is not None and self._index.available
        ingredients_block: List[Dict[str, object]] = []
        id_map: Dict[str, str] = {}  # send_id -> ref.key
        union: Dict[str, _FoodCandidate] = {}  # internal_id -> candidate
        for ref in refs:
            send_id = ref.ingredient.id or ref.key
            id_map[send_id] = ref.key
            candidates = self._shortlist_candidates(ref)
            for candidate in candidates:
                union[candidate.internal_id] = candidate
            entry: Dict[str, object] = {"ingredientId": send_id, "name": ref.ingredient.name}
            if per_ingredient:
                entry["candidateIds"] = [candidate.internal_id for candidate in candidates]
            ingredients_block.append(entry)

        if not union:
            return result

        candidate_lines = [self._candidate_detail_line(candidate) for candidate in union.values()]

        replacements = {
            "ingredient": refs[0].ingredient.name if refs else "",
            "candidates": "\n".join(candidate_lines) if candidate_lines else "-",
            "ingredients": json.dumps({"ingredients": ingredients_block}, ensure_ascii=False),
        }
        prompt_cfg = resolve_prompt("ingredients", self._locale, replacements=replacements)
        llm_cfg = resolve_llm_config("ingredients")
        logger.info("LLM config (ingredients): %s", format_llm_log(llm_cfg, self._llm_config))
        system_prompt = (prompt_cfg.get("system") or _SYSTEM_PROMPT).strip() or _SYSTEM_PROMPT
        user_parts = [
            part.strip()
            for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
            if part and part.strip()
        ]
        user_prompt = "\n\n".join(user_parts).strip() or json.dumps(
            {"ingredients": ingredients_block, "candidates": candidate_lines}, ensure_ascii=False
        )

        try:
            log_prompt_messages(
                "ingredients",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            data = self._llm_client.run_json(system_prompt or _SYSTEM_PROMPT, user_prompt, llm_config=llm_cfg)
        except Exception as exc:  # pragma: no cover - external dependency
            logger.debug("Assistant lookup failed: %s", exc)
            return result

        links = data.get("links") if isinstance(data, dict) else None
        if not isinstance(links, list):
            logger.debug("Assistant response did not contain 'links'")
            return result

        for link in links:
            if not isinstance(link, dict):
                continue
            ing_id = link.get("ingredientId")
            food_internal_id = link.get("foodId")
            if not ing_id or not isinstance(ing_id, str):
                continue
            ref_key = id_map.get(ing_id)
            if not ref_key:
                continue
            if food_internal_id is None:
                result[ref_key] = None
                continue
            if not isinstance(food_internal_id, str):
                continue
            mealie_id = self._internal_map.get(food_internal_id)
            if mealie_id:
                result[ref_key] = mealie_id
        return result

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
        match_details: Dict[str, Dict[str, object]],  # noqa: ARG002 - kept for future use / debugging
        missing: List[IngredientRef],
        suggestions: Dict[str, Dict[str, object]],
        new_ids: Dict[str, str],
    ) -> None:
        recorder = context.pipeline_recorder
        if not recorder:
            logger.debug("No pipeline recorder available, so no foods review file was created")
            return

        items: List[Dict[str, object]] = []

        for ref in ingredient_refs:
            ingredient = ref.ingredient
            key = ref.key
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

            items.append(
                {
                    "key": key,
                    "newId": new_ids.get(key),
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
        new_ids: Dict[str, str],
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
                ingredient.food_new_id = None
            elif ref.key in missing_keys:
                ingredient.food_badge_id = STATUS_NEW
                ingredient.food_new_id = new_ids.get(ref.key)
                ingredient.mealie_food_id = None
            else:
                ingredient.food_badge_id = STATUS_NONE
                ingredient.food_new_id = None
        context.update_recipe_file()

    @staticmethod
    def _badge_for_strategy(strategy: Optional[object]) -> str:
        if strategy == "exact" or strategy == "preassigned":
            return STATUS_FOUND_WORD
        if strategy == "embedding" or strategy == "fuzzy":
            return STATUS_FOUND_FUZZY
        if strategy == "ai":
            return STATUS_FOUND_AI
        return STATUS_FOUND_WORD

    @staticmethod
    def _build_new_id(kind: str, ref: IngredientRef) -> str:
        safe_key = ref.key.replace(":", "-")
        return f"{kind}-new-{safe_key}"

    # ------------------------------------------------------------------
    def _candidate_names(self, candidate: _FoodCandidate) -> Iterable[str]:
        yield candidate.name
        if candidate.plural:
            yield candidate.plural
        for alias in candidate.aliases:
            yield alias

    def _foods_dict(self) -> Dict[str, _FoodCandidate]:
        return {item.id: item for item in self._foods}

    def _foods_by_internal(self) -> Dict[str, _FoodCandidate]:
        return {item.internal_id: item for item in self._foods if item.internal_id}

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
