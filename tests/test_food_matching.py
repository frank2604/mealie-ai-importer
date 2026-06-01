"""Food matching logic (stage-one normalized + stage-two shortlist+LLM)."""
from types import SimpleNamespace

from importer.modules.food_checker.food_checker import (
    FoodCheckerModule,
    _FoodCandidate,
    STATUS_FOUND_WORD,
    STATUS_FOUND_FUZZY,
    STATUS_FOUND_AI,
)


def _module():
    m = FoodCheckerModule(ingredient_service=None, llm_client=None, locale="de")
    m._foods = [
        _FoodCandidate(id="f1", internal_id="1", name="Saure Sahne", plural="Saure Sahne", aliases=["Schmand"]),
        _FoodCandidate(id="f2", internal_id="2", name="Zwiebel", plural="Zwiebeln", aliases=[]),
        _FoodCandidate(id="f3", internal_id="3", name="Zucker", plural="Zucker", aliases=[]),
    ]
    m._internal_map = {c.internal_id: c.id for c in m._foods}
    m._normalized_lookup = m._build_normalized_lookup()
    return m


def test_stage_one_normalized_exact_with_qualifier_and_alias():
    m = _module()
    assert m._stage_one_match("Zwiebeln")[0] == "f2"
    assert m._stage_one_match("frische Zwiebeln")[0] == "f2"
    assert m._stage_one_match("Schmand")[0] == "f1"  # alias
    assert m._stage_one_match("Pfeffer")[0] is None


def test_candidate_detail_line_includes_plural_and_aliases():
    m = _module()
    line_onion = m._candidate_detail_line(m._foods[1])
    assert "Plural: Zwiebeln" in line_onion
    line_cream = m._candidate_detail_line(m._foods[0])
    assert "Aliase: Schmand" in line_cream


def test_stage_two_shortlist_maps_internal_to_mealie_id():
    m = _module()

    class StubIndex:
        available = True

        def shortlist(self, q, k=5):
            return [("f1", 0.9), ("f3", 0.2)]

    m._index = StubIndex()
    captured = {}

    class FakeLLM:
        def run_json(self, system, user, *, llm_config=None):
            captured["user"] = user
            return {"links": [{"ingredientId": "i1", "foodId": "1"}]}

    m._llm_client = FakeLLM()
    ref = SimpleNamespace(key="0:0", ingredient=SimpleNamespace(id="i1", name="Crème fraîche"))
    result = m._stage_two_batch_with_llm([ref])
    assert result["0:0"] == "f1"
    assert '"candidateIds"' in captured["user"]  # per-ingredient shortlist sent


def test_stage_two_fallback_without_embeddings():
    m = _module()

    class OffIndex:
        available = False

        def shortlist(self, q, k=5):
            return []

    m._index = OffIndex()
    captured = {}

    class FakeLLM:
        def run_json(self, system, user, *, llm_config=None):
            captured["user"] = user
            return {"links": [{"ingredientId": "i1", "foodId": "1"}]}

    m._llm_client = FakeLLM()
    ref = SimpleNamespace(key="0:0", ingredient=SimpleNamespace(id="i1", name="Crème fraîche"))
    result = m._stage_two_batch_with_llm([ref])
    assert result["0:0"] == "f1"
    assert '"candidateIds"' not in captured["user"]  # full-list fallback


def test_badge_mapping_stays_within_allowed_values():
    allowed = {STATUS_FOUND_WORD, STATUS_FOUND_FUZZY, STATUS_FOUND_AI}
    assert FoodCheckerModule._badge_for_strategy("exact") == STATUS_FOUND_WORD
    assert FoodCheckerModule._badge_for_strategy("embedding") == STATUS_FOUND_FUZZY
    assert FoodCheckerModule._badge_for_strategy("ai") == STATUS_FOUND_AI
    assert FoodCheckerModule._badge_for_strategy("anything") in allowed
