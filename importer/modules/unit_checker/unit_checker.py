"""Match ingredient units against Mealie's unit definitions."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional

from ..context import IngredientRef, PipelineContext
from ...llm_parser import OpenAiClient
from ...services.ingredients import IngredientService

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Du ordnest Einheiten aus einem Rezept vorhandenen Mealie-Einheiten zu. "
    "Wähle nur dann eine Einheit, wenn sie eindeutig passt und beachte Abkürzungen."
)


@dataclass
class _UnitCandidate:
    id: str
    name: str
    plural: str
    abbreviation: str
    plural_abbreviation: str

    @classmethod
    def from_raw(cls, raw: Dict[str, object]) -> "_UnitCandidate":
        return cls(
            id=str(raw.get("id") or ""),
            name=str(raw.get("name") or ""),
            plural=str(raw.get("pluralName") or raw.get("name") or ""),
            abbreviation=str(raw.get("abbreviation") or ""),
            plural_abbreviation=str(raw.get("pluralAbbreviation") or ""),
        )


class UnitCheckerModule:
    """Check ingredient units against Mealie caches."""

    name = "Unit checker"

    def __init__(
        self,
        ingredient_service: Optional[IngredientService],
        *,
        llm_client: Optional[OpenAiClient] = None,
    ) -> None:
        self._service = ingredient_service
        self._llm_client = llm_client
        self._units: List[_UnitCandidate] = []

    def run(self, context: PipelineContext) -> None:
        ingredient_refs = [ref for ref in context.iter_ingredients() if ref.ingredient.unit]
        logger.info("Prüfe %s Einheiten gegen Mealie", len(ingredient_refs))

        reference = self._load_reference_data(context)
        self._write_cache(reference, context)

        matches: Dict[str, str] = {}
        missing: List[IngredientRef] = []

        for ref in ingredient_refs:
            ingredient = ref.ingredient
            if ingredient.mealie_unit_id:
                matches[ref.key] = ingredient.mealie_unit_id
                continue

            candidate_id = self._stage_one_match(ingredient.unit or "")
            if candidate_id:
                matches[ref.key] = candidate_id
                continue

            candidate_id = self._stage_two_with_llm(ingredient.unit or "")
            if candidate_id:
                matches[ref.key] = candidate_id
            else:
                missing.append(ref)

        context.unit_matches = matches
        context.missing_unit_refs = missing
        logger.info("%s Einheiten gefunden, %s fehlen", len(matches), len(missing))

    # ------------------------------------------------------------------
    # Reference data handling
    # ------------------------------------------------------------------
    def _load_reference_data(self, context: PipelineContext) -> Dict[str, object]:
        if self._service:
            self._service.refresh_units()
            units = [
                _UnitCandidate.from_raw(item)
                for item in self._service.list_units()
                if item.get("id")
            ]
        else:
            units = []

        if not units:
            cache_path = context.cache_paths.units_cache
            if cache_path.exists():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    logger.debug("Alte MealieUnitsCache.json ignoriert – kein gültiges JSON")
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
    def _stage_one_match(self, query: str) -> Optional[str]:
        if not query:
            return None
        if self._service:
            resource = self._service.lookup_unit(query)
            if resource:
                return resource.id
        return self._fuzzy_match_offline(query)

    def _fuzzy_match_offline(self, query: str) -> Optional[str]:
        if not self._units:
            return None
        best_id: Optional[str] = None
        best_score = 0.0
        normalized_query = query.strip().lower()
        for candidate in self._units:
            for option in self._candidate_names(candidate):
                normalized_option = option.lower()
                if normalized_option == normalized_query:
                    return candidate.id
                score = SequenceMatcher(None, normalized_query, normalized_option).ratio()
                if score > best_score:
                    best_score = score
                    best_id = candidate.id
        if best_score >= 0.9:
            return best_id
        return None

    def _stage_two_with_llm(self, query: str) -> Optional[str]:
        if not self._llm_client or not self._units:
            return None

        candidates = self._top_candidates(query, limit=8)
        if not candidates:
            return None

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
        user_prompt = (
            f"Einheit: {query}\n"
            "Kandidaten:\n"
            + "\n".join(candidate_lines)
            + "\nAntwortformat: {\"match\": <ID oder null>}"
        )

        try:
            response = self._llm_client.run_text(_SYSTEM_PROMPT, user_prompt)
        except Exception as exc:  # pragma: no cover - external dependency
            logger.debug("LLM-Einheitenabgleich fehlgeschlagen: %s", exc)
            return None

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.debug("LLM Antwort kein JSON: %s", response[:120])
            return None

        match_id = data.get("match")
        if not isinstance(match_id, str):
            return None

        known_ids = {candidate.id for candidate in candidates}
        if match_id not in known_ids:
            logger.debug("LLM schlug unbekannte Einheit %s vor", match_id)
            return None
        return match_id

    def _top_candidates(self, query: str, *, limit: int) -> List[_UnitCandidate]:
        scored: List[tuple[float, _UnitCandidate]] = []
        normalized_query = query.strip().lower()
        for candidate in self._units:
            best_score = 0.0
            for option in self._candidate_names(candidate):
                score = SequenceMatcher(None, normalized_query, option.lower()).ratio()
                if score > best_score:
                    best_score = score
            if best_score > 0:
                scored.append((best_score, candidate))
        scored.sort(key=lambda item: item[0], reverse=True)
        unique: List[_UnitCandidate] = []
        seen_ids = set()
        for _, candidate in scored:
            if candidate.id in seen_ids:
                continue
            unique.append(candidate)
            seen_ids.add(candidate.id)
            if len(unique) >= limit:
                break
        return unique

    def _candidate_names(self, candidate: _UnitCandidate) -> Iterable[str]:
        yield candidate.name
        if candidate.plural:
            yield candidate.plural
        if candidate.abbreviation:
            yield candidate.abbreviation
        if candidate.plural_abbreviation:
            yield candidate.plural_abbreviation

