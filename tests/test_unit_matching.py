"""Unit matching logic (normalized canonical, EL/TL strictly separate)."""
from importer.modules.unit_checker.unit_checker import UnitCheckerModule, _UnitCandidate


def _module():
    m = UnitCheckerModule(ingredient_service=None, llm_client=None, locale="de")
    m._units = [
        _UnitCandidate(id="u1", name="Gramm", plural="Gramm", abbreviation="g", plural_abbreviation=""),
        _UnitCandidate(id="u2", name="Esslöffel", plural="Esslöffel", abbreviation="EL", plural_abbreviation=""),
        _UnitCandidate(id="u3", name="Teelöffel", plural="Teelöffel", abbreviation="TL", plural_abbreviation=""),
    ]
    return m


def test_exact_and_canonical_variants():
    m = _module()
    assert m._stage_one_match("Gramm")[0] == "u1"
    assert m._stage_one_match("gr")[0] == "u1"
    assert m._stage_one_match("g")[0] == "u1"
    assert m._stage_one_match("Esslöffel")[0] == "u2"
    assert m._stage_one_match("EL")[0] == "u2"


def test_el_tl_never_cross():
    m = _module()
    assert m._stage_one_match("TL")[0] == "u3"
    assert m._stage_one_match("el")[0] == "u2"
    assert m._stage_one_match("tl")[0] == "u3"


def test_unknown_unit_returns_none():
    m = _module()
    assert m._stage_one_match("Furlong")[0] is None


def test_llm_fallback_uses_run_json():
    m = _module()

    class FakeLLM:
        def run_json(self, system, user, *, llm_config=None):
            return {"match": "u1"}

    m._llm_client = FakeLLM()
    unit_id, _label = m._stage_two_with_llm("Gewichtseinheit")
    assert unit_id == "u1"
