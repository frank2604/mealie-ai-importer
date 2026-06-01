import pytest

from importer.services.unit_norm import canonical_unit, variants_for, CANONICAL_UNITS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("g", "g"), ("gr", "g"), ("Gramm", "g"), ("gramm", "g"),
        ("kg", "kg"), ("Kilo", "kg"),
        ("ml", "ml"), ("Milliliter", "ml"),
        ("Esslöffel", "EL"), ("el", "EL"), ("EL", "EL"),
        ("Teelöffel", "TL"), ("tl", "TL"),
        ("Pck.", "Packung"), ("päckchen", "Packung"),
        ("Stk", "Stück"),
    ],
)
def test_canonical_mapping(raw, expected):
    assert canonical_unit(raw) == expected


def test_el_and_tl_never_cross():
    # The single most important invariant: spoon units stay distinct.
    assert canonical_unit("EL") == "EL"
    assert canonical_unit("TL") == "TL"
    assert canonical_unit("EL") != canonical_unit("TL")
    assert "el" not in variants_for("TL")
    assert "tl" not in variants_for("EL")


def test_unknown_returns_none():
    assert canonical_unit("Furlong") is None
    assert canonical_unit("") is None


def test_no_variant_shared_between_two_canonicals():
    # Guards against future edits accidentally cross-mapping a variant.
    seen = {}
    for canonical, variants in CANONICAL_UNITS.items():
        for variant in [canonical.lower(), *(v.lower() for v in variants)]:
            assert seen.get(variant, canonical) == canonical, variant
            seen[variant] = canonical
