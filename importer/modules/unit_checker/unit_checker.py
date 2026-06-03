"""Match ingredient units against Mealie's unit definitions."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ..context import IngredientRef, PipelineContext
from ...llm_parser import OpenAiClient
from ...config import LlmConfig
from ...prompt_store import resolve_prompt, resolve_llm_config
from ...prompt_logging import log_prompt_messages
from ...llm_utils import format_llm_log
from ...services.ingredients import IngredientService
from ...services.text_norm import normalize_de
from ...services.unit_norm import canonical_unit

logger = logging.getLogger("Unit Checker")

STATUS_FOUND_WORD = "found_word"
STATUS_FOUND_FUZZY = "found_fuzzy"
STATUS_FOUND_AI = "found_ai"
STATUS_NEW = "new"
STATUS_NONE = "none"

_SYSTEM_PROMPT = (
    "Du ordnest Einheiten aus einem Rezept den vorhandenen Mealie-Einheiten zu. "
    "Wähle nur eine Einheit, wenn sie eindeutig passt, und antworte ausschließlich im JSON-Format "
    '{"match": <ID oder null>}."'
)


@dataclass
class _UnitCandidate:
    id: str
    name: str
    plural: str
    abbreviation: str
    plural_abbreviation: str
    aliases: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.aliases is None:
            self.aliases = []

    @classmethod
    def from_raw(cls, raw: Dict[str, object]) -> "_UnitCandidate":
        return cls(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            plural=str(raw.get("pluralName") or raw.get("name") or ""),
            abbreviation=str(raw.get("abbreviation") or ""),
            plural_abbreviation=str(raw.get("pluralAbbreviation") or ""),
            aliases=[
                alias["name"] if isinstance(alias, dict) else str(alias)
                for alias in (raw.get("aliases") or [])
                if (alias["name"] if isinstance(alias, dict) else str(alias)).strip()
            ],
        )


class UnitCheckerModule:
    """Check ingredient units against Mealie caches."""

    name = "Unit Checker"

    def __init__(
        self,
        ingredient_service: Optional[IngredientService],
        *,
        llm_client: Optional[OpenAiClient] = None,
        llm_config: Optional[LlmConfig] = None,
        locale: str = "de",
    ) -> None:
        self._service = ingredient_service
        self._llm_client = llm_client
        self._units: List[_UnitCandidate] = []
        self._locale = locale or "de"
        self._llm_config = llm_config

    def run(self, context: PipelineContext) -> None:
        ingredient_refs = [
            ref for ref in context.iter_ingredients() if ref.ingredient.unit or ref.ingredient.unit_original_name
        ]
        total = len(ingredient_refs)
        if total == 0:
            logger.info("No units found on the ingredients, so we skip the unit checker")
            return

        grouped_refs: Dict[str, List[IngredientRef]] = {}
        group_order: List[str] = []
        for ref in ingredient_refs:
            unit_name = ref.ingredient.unit or ref.ingredient.unit_original_name or ""
            normalized = self._normalize_unit(unit_name)
            if normalized not in grouped_refs:
                grouped_refs[normalized] = []
                group_order.append(normalized)
            grouped_refs[normalized].append(ref)

        unique_unit_names = [
            grouped_refs[key][0].ingredient.unit or grouped_refs[key][0].ingredient.unit_original_name or ""
            for key in group_order
        ]
        unique_total = len(unique_unit_names)
        logger.info(
            "Trying to match %s unique unit%s (from %s ingredient entr%s) to existing Mealie units %s",
            unique_total,
            "" if unique_total == 1 else "s",
            total,
            "y" if total == 1 else "ies",
            self._format_list(unique_unit_names),
        )

        reference = self._load_reference_data(context)
        self._write_cache(reference, context)
        units_by_id = self._units_dict()

        matches: Dict[str, str] = {}
        match_details: Dict[str, Dict[str, object]] = {}
        exact_matches: List[str] = []
        fuzzy_matches: List[tuple[str, str]] = []
        ai_matches: List[tuple[str, str]] = []
        pending_ai_groups: List[tuple[str, List[IngredientRef]]] = []

        for normalized in group_order:
            refs = grouped_refs[normalized]
            if not refs:
                continue
            preassigned_refs = [ref for ref in refs if ref.ingredient.mealie_unit_id]
            for ref in preassigned_refs:
                unit_name = ref.ingredient.unit or ref.ingredient.unit_original_name or ""
                if not unit_name:
                    unit_name = "(unbekannt)"
                unit_id = ref.ingredient.mealie_unit_id or ""
                matches[ref.key] = unit_id
                match_details[ref.key] = {"strategy": "preassigned"}
                exact_matches.append(unit_name)

            pending_refs = [ref for ref in refs if not ref.ingredient.mealie_unit_id]
            if not pending_refs:
                continue

            sample_unit = pending_refs[0].ingredient.unit or pending_refs[0].ingredient.unit_original_name or ""
            candidate_id, strategy, matched_label = self._stage_one_match(sample_unit)
            if candidate_id:
                candidate = units_by_id.get(candidate_id)
                display = matched_label or (candidate.name if candidate else candidate_id)
                for ref in pending_refs:
                    unit_name = ref.ingredient.unit or ""
                    matches[ref.key] = candidate_id
                    match_details[ref.key] = {"strategy": strategy}
                    if strategy == "exact":
                        exact_matches.append(display or unit_name or "(unbekannt)")
                    else:
                        fuzzy_matches.append((unit_name, display))
                continue

            pending_ai_groups.append((sample_unit, pending_refs))

        missing: List[IngredientRef] = []
        unresolved_units: List[str] = []
        unresolved_seen: set[str] = set()

        if exact_matches:
            logger.info(
                "Matched %s unit%s exact by words: %s",
                len(exact_matches),
                "" if len(exact_matches) == 1 else "s",
                self._format_list(sorted(exact_matches, key=lambda value: value.lower())),
            )
        if fuzzy_matches:
            logger.info(
                "Matched %s unit%s with Fuzzy-Search: %s",
                len(fuzzy_matches),
                "" if len(fuzzy_matches) == 1 else "s",
                self._format_fuzzy_pairs(fuzzy_matches),
            )

        if pending_ai_groups:
            pending_names = [name for name, _ in pending_ai_groups]
            logger.info(
                "Try matching rest of the units %s with AI",
                self._format_list(pending_names),
            )

        for display_name, refs in pending_ai_groups:
            unit_name = display_name
            logger.info(
                "Ask AI to find [%s] in existing units in Mealie",
                unit_name,
            )
            candidate_id, candidate_name = self._stage_two_with_llm(unit_name)
            if candidate_id:
                for ref in refs:
                    unit_value = ref.ingredient.unit or ""
                    matches[ref.key] = candidate_id
                    match_details[ref.key] = {"strategy": "ai"}
                    ai_matches.append((unit_value, candidate_name or candidate_id))
                logger.info(
                    "AI suggests [%s] from existing units in Mealie",
                    candidate_name or candidate_id,
                )
            else:
                logger.info(
                    "AI could not find a matching unit for [%s] in existing units in Mealie",
                    unit_name,
                )
                missing.extend(refs)
                if display_name not in unresolved_seen:
                    unresolved_seen.add(display_name)
                    unresolved_units.append(display_name)

        context.unit_matches = matches
        context.missing_unit_refs = missing
        new_ids = {ref.key: self._build_new_id("unit", ref) for ref in missing}
        self._update_recipe_matches(context, ingredient_refs, matches, match_details, missing, new_ids)

        logger.info(
            "Matched %s unit%s so far; %s still need attention",
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
        if unresolved_units and self._service:
            logger.info("Will ask AI for naming suggestions for missing units")
            for name in unresolved_units:
                logger.info(
                    "Ask AI for name, plural and abbreviations for unit [%s]",
                    name,
                )
            try:
                self._service.prepare_unit_forms(
                    unresolved_units,
                    debug=context.pipeline_recorder,
                )
            except Exception as exc:  # pragma: no cover - external dependency
                logger.debug("Could not prepare unit-form suggestions: %s", exc)
            try:
                suggestions = self._service.unit_form_suggestions(
                    unresolved_units,
                    debug=context.pipeline_recorder,
                )
            except Exception as exc:  # pragma: no cover - external dependency
                logger.debug("Could not retrieve unit-form suggestions: %s", exc)
            for name in unresolved_units:
                suggestion = suggestions.get(name)
                if suggestion:
                    logger.info(
                        "AI returns this suggestion for unit [%s]: name [%s], plural [%s], abbreviation [%s], plural abbreviation [%s], use abbreviation [%s]",
                        name,
                        suggestion.get("name") or "-",
                        suggestion.get("pluralName") or "-",
                        suggestion.get("abbreviation") or "-",
                        suggestion.get("pluralAbbreviation") or "-",
                        suggestion.get("useAbbreviation"),
                    )
                else:
                    logger.info(
                        "AI could not generate a unit suggestion for [%s]",
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
        units: List[_UnitCandidate] = []

        if self._service:
            units = [
                _UnitCandidate.from_raw(item)
                for item in self._service.list_units()
                if item.get("id")
            ]

        if not units:
            cache_path = context.cache_paths.units_cache
            if cache_path.exists():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    logger.debug("Ignoring MealieUnitsCache.json because it is not valid JSON")
                else:
                    units = [
                        _UnitCandidate.from_raw(item)
                        for item in cached.get("units", [])
                        if item.get("id")
                    ]

        self._units = units
        return {
            "units": [
                {
                    "id": item.id,
                    "name": item.name,
                    "pluralName": item.plural,
                    "abbreviation": item.abbreviation,
                    "pluralAbbreviation": item.plural_abbreviation,
                }
                for item in units
            ]
        }

    def _write_cache(self, snapshot: Dict[str, object], context: PipelineContext) -> None:
        payload = {"updated_at": datetime.utcnow().isoformat(), **snapshot}
        context.cache_paths.units_cache.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------
    def _stage_one_match(self, query: str) -> tuple[Optional[str], str, Optional[str]]:
        if not query:
            return None, "exact", None
        match_id, match_label = self._exact_match(query)
        if match_id:
            return match_id, "exact", match_label
        # Normalize spelling variants (g/gr/Gramm, EL/Esslöffel, ...) to a
        # canonical token and match that against the Mealie units. This is a
        # deterministic table lookup, not fuzzy similarity, so EL and TL can
        # never be confused.
        canonical = canonical_unit(query)
        if canonical:
            canonical_id, canonical_label = self._canonical_match(canonical)
            if canonical_id:
                return canonical_id, "exact", canonical_label
        return None, "exact", None

    def _exact_match(self, query: str) -> tuple[Optional[str], Optional[str]]:
        normalized = normalize_de(query)
        if not normalized:
            return None, None
        for candidate in self._units:
            for option in self._candidate_names(candidate):
                if normalize_de(option) == normalized:
                    return candidate.id, option
        return None, None

    def _canonical_match(self, canonical: str) -> tuple[Optional[str], Optional[str]]:
        """Find a Mealie unit whose name/abbreviation maps to *canonical*."""
        canonical_norm = normalize_de(canonical)
        for candidate in self._units:
            for option in self._candidate_names(candidate):
                if canonical_unit(option) == canonical or normalize_de(option) == canonical_norm:
                    return candidate.id, option
        return None, None

    def _stage_two_with_llm(self, query: str) -> tuple[Optional[str], Optional[str]]:
        if not self._llm_client or not self._units:
            return None, None

        candidates = list(self._units)
        if not candidates:
            return None, None

        candidate_lines = []
        for candidate in candidates:
            candidate_lines.append(
                "- {id}: {name} (Plural: {plural}; Abk.: {abbr}; Plural-Abk.: {pabbr})".format(
                    id=candidate.id,
                    name=candidate.name,
                    plural=candidate.plural,
                    abbr=candidate.abbreviation or "-",
                    pabbr=candidate.plural_abbreviation or "-",
                )
            )
        replacements = {
            "unit": query,
            "candidates": "\n".join(candidate_lines) if candidate_lines else "-",
        }
        prompt_cfg = resolve_prompt("units", self._locale, replacements=replacements)
        llm_cfg = resolve_llm_config("units")
        logger.info("LLM config (units): %s", format_llm_log(llm_cfg, self._llm_config))
        system_prompt = prompt_cfg.get("system", _SYSTEM_PROMPT).strip() or _SYSTEM_PROMPT
        user_parts = [
            part.strip()
            for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
            if part and part.strip()
        ]
        user_prompt = "\n\n".join(user_parts).strip() or "\n".join(candidate_lines)

        try:
            log_prompt_messages(
                "units",
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            data = self._llm_client.run_json(system_prompt or _SYSTEM_PROMPT, user_prompt, llm_config=llm_cfg)
        except Exception as exc:  # pragma: no cover - external dependency
            logger.debug("Assistant unit lookup failed: %s", exc)
            return None, None

        if not isinstance(data, dict):
            logger.debug("Assistant unit response was not a JSON object")
            return None, None

        match_id = data.get("match")
        if not isinstance(match_id, str):
            logger.debug('The assistant could not find a confident unit for "%s"', query)
            return None, None

        known_ids = {candidate.id for candidate in candidates}
        if match_id not in known_ids:
            logger.debug("The assistant suggested an unknown unit id %s", match_id)
            return None, None

        unit = self._units_dict().get(match_id)
        return match_id, (unit.name if unit else None)

    # ------------------------------------------------------------------
    # Review and reporting
    # ------------------------------------------------------------------
    def _log_stats(
        self,
        exact_matches: List[str],
        fuzzy_matches: List[tuple[str, str]],
        ai_matches: List[tuple[str, str]],
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
                "Matched %s unit%s exact by words: %s",
                len(exact_matches),
                "" if len(exact_matches) == 1 else "s",
                self._format_list(sorted(exact_matches, key=lambda value: value.lower())),
            )
        if include_stage_one and fuzzy_matches:
            logger.info(
                "Matched %s unit%s with Fuzzy-Search: %s",
                len(fuzzy_matches),
                "" if len(fuzzy_matches) == 1 else "s",
                self._format_fuzzy_pairs(fuzzy_matches),
            )
        if ai_matches:
            logger.info(
                "Matched %s unit%s with AI: %s",
                len(ai_matches),
                "" if len(ai_matches) == 1 else "s",
                self._format_ai_pairs(ai_matches),
            )
        if missing:
            unique_missing: Dict[str, str] = {}
            for ref in missing:
                unit_name = ref.ingredient.unit or ref.ingredient.unit_original_name or ""
                normalized = self._normalize_unit(unit_name)
                if normalized not in unique_missing:
                    unique_missing[normalized] = unit_name
            logger.info(
                "%s unit%s need to be created in Mealie: %s",
                len(unique_missing),
                "" if len(unique_missing) == 1 else "s",
                self._format_list(unique_missing.values()),
            )
        else:
            logger.info("Every unit now has a Mealie match")

    def _write_review(
        self,
        context: PipelineContext,
        ingredient_refs: List[IngredientRef],
        matches: Dict[str, str],  # noqa: ARG002 - reserved for future enhancements
        match_details: Dict[str, Dict[str, object]],  # noqa: ARG002
        missing: List[IngredientRef],
        suggestions: Dict[str, Dict[str, object]],
        new_ids: Dict[str, str],
    ) -> None:
        recorder = context.pipeline_recorder
        if not recorder:
            logger.debug("No pipeline recorder available, so no units review file was created")
            return

        items: List[Dict[str, object]] = []
        for ref in ingredient_refs:
            ingredient = ref.ingredient
            key = ref.key
            # Try to resolve suggestions using unit text, original name, or normalized variants
            suggestion = None
            for candidate in [
                ingredient.unit,
                ingredient.unit_original_name,
                (ingredient.unit or "").lower(),
                (ingredient.unit_original_name or "").lower(),
            ]:
                if candidate and candidate in suggestions:
                    suggestion = suggestions[candidate]
                    break
            create_defaults = {
                "name": None,
                "pluralName": None,
                "abbreviation": None,
                "pluralAbbreviation": None,
                "useAbbreviation": False,
            }
            if suggestion:
                create_defaults.update(
                    {
                        "name": suggestion.get("name"),
                        "pluralName": suggestion.get("pluralName"),
                        "abbreviation": suggestion.get("abbreviation"),
                        "pluralAbbreviation": suggestion.get("pluralAbbreviation"),
                        "useAbbreviation": bool(suggestion.get("useAbbreviation")),
                    }
                )

            items.append(
                {
                    "key": key,
                    "newId": new_ids.get(key),
                    "suggestion": suggestion,
                    "userDecision": {
                        "action": "auto",
                        "useUnitId": None,
                        "create": create_defaults,
                        "notes": "",
                    },
                }
            )

        payload = {
            "generatedAt": datetime.utcnow().isoformat(),
            "units": items,
        }

        review_path = recorder.write_json("UnitsReview", payload)
        context.unit_review_path = review_path
        context.unit_decisions = {}
        logger.info("Saved the units review to %s", review_path)

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
            ingredient.mealie_unit_id = match_id
            if match_id:
                strategy = (match_details.get(ref.key) or {}).get("strategy")
                ingredient.unit_badge_id = self._badge_for_strategy(strategy)
                ingredient.unit_new_id = None
            elif ref.key in missing_keys:
                ingredient.unit_badge_id = STATUS_NEW
                ingredient.unit_new_id = new_ids.get(ref.key)
                ingredient.mealie_unit_id = None
            else:
                ingredient.unit_badge_id = STATUS_NONE
                ingredient.unit_new_id = None
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

    @staticmethod
    def _build_new_id(kind: str, ref: IngredientRef) -> str:
        safe_key = ref.key.replace(":", "-")
        return f"{kind}-new-{safe_key}"

    # ------------------------------------------------------------------
    def _candidate_names(self, candidate: _UnitCandidate) -> Iterable[str]:
        yield candidate.name
        if candidate.plural:
            yield candidate.plural
        if candidate.abbreviation:
            yield candidate.abbreviation
        if candidate.plural_abbreviation:
            yield candidate.plural_abbreviation
        for alias in (candidate.aliases or []):
            if alias:
                yield alias

    def _units_dict(self) -> Dict[str, _UnitCandidate]:
        return {item.id: item for item in self._units}

    @staticmethod
    def _format_list(values: Iterable[str]) -> str:
        cleaned = [str(value) for value in values if value]
        if not cleaned:
            return "[]"
        return "[" + ", ".join(cleaned) + "]"

    @staticmethod
    def _normalize_unit(value: str) -> str:
        return (value or "").strip().lower()

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

    @staticmethod
    def _format_ai_pairs(pairs: Iterable[tuple[str, str]]) -> str:
        entries = [
            f"[{source}] -> [{target}]"
            for source, target in pairs
            if source and target
        ]
        if not entries:
            return "[]"
        return ", ".join(entries)
