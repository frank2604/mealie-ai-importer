"""Match recipe ingredients against existing Mealie foods."""
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
    "Du vergleichst Zutaten aus einem Rezept mit vorhandenen Lebensmitteln. "
    "Wähle nur ein Lebensmittel, wenn es eindeutig passt. Antworte immer mit JSON."
)


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

    name = "Food checker"

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
        logger.info("Prüfe %s Zutaten gegen Mealie-Lebensmittel", len(ingredient_refs))

        reference = self._load_reference_data(context)
        self._write_cache(reference, context)

        matches: Dict[str, str] = {}
        missing: List[IngredientRef] = []

        for ref in ingredient_refs:
            ingredient = ref.ingredient
            if ingredient.mealie_food_id:
                matches[ref.key] = ingredient.mealie_food_id
                continue

            candidate_id = self._stage_one_match(ingredient.name)
            if candidate_id:
                matches[ref.key] = candidate_id
                continue

            candidate_id = self._stage_two_with_llm(ingredient.name)
            if candidate_id:
                matches[ref.key] = candidate_id
            else:
                missing.append(ref)

        context.food_matches = matches
        context.missing_food_refs = missing
        logger.info("%s Zutaten gefunden, %s verbleiben ohne Zuordnung", len(matches), len(missing))

    # ------------------------------------------------------------------
    # Reference data handling
    # ------------------------------------------------------------------
    def _load_reference_data(self, context: PipelineContext) -> Dict[str, object]:
        if self._service:
            self._service.refresh()
            foods = [
                _FoodCandidate.from_raw(item)
                for item in self._service.list_foods()
                if item.get("id")
            ]
            categories = list(self._service.list_food_categories())
        else:
            foods = []
            categories = []

        if not foods:
            cache_path = context.cache_paths.foods_cache
            if cache_path.exists():
                try:
                    cached = json.loads(cache_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    logger.debug("Alte MealieFoodsCache.json ignoriert – kein gültiges JSON")
                else:
                    foods = [
                        _FoodCandidate.from_raw(item)
                        for item in cached.get("foods", [])
                        if item.get("id")
                    ]
                    categories = list(cached.get("categories", []))

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
        payload = {
            "updated_at": datetime.utcnow().isoformat(),
            **snapshot,
        }
        context.cache_paths.foods_cache.write_text(
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
            resource = self._service.lookup_food(query)
            if resource:
                return resource.id
        return self._fuzzy_match_offline(query)

    def _fuzzy_match_offline(self, query: str) -> Optional[str]:
        if not self._foods:
            return None
        best_id: Optional[str] = None
        best_score = 0.0
        normalized_query = query.strip().lower()
        for candidate in self._foods:
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
        if not self._llm_client or not self._foods:
            return None

        candidates = self._top_candidates(query, limit=10)
        if not candidates:
            return None

        candidate_lines = []
        for candidate in candidates:
            alias_part = ", ".join(candidate.aliases) if candidate.aliases else "-"
            candidate_lines.append(
                f"- {candidate.id}: {candidate.name} (Plural: {candidate.plural}; Aliasse: {alias_part})"
            )
        user_prompt = (
            f"Zutat: {query}\n"
            "Kandidaten:\n"
            + "\n".join(candidate_lines)
            + "\nAntwortformat: {\"match\": <ID oder null>, \"reason\": string}"
        )

        try:
            response = self._llm_client.run_text(_SYSTEM_PROMPT, user_prompt)
        except Exception as exc:  # pragma: no cover - HTTP failures handled upstream
            logger.debug("LLM-Abgleich fehlgeschlagen: %s", exc)
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
            logger.debug("LLM schlug unbekannte ID %s vor", match_id)
            return None
        return match_id

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
        seen_ids = set()
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

