from importer.services.text_norm import normalize_de, fold_umlauts, strip_qualifiers, tokens


def test_lowercase_and_whitespace():
    assert normalize_de("  Saure   Sahne ") == "saure sahne"


def test_strips_preparation_qualifiers():
    assert normalize_de("Frische Zwiebeln") == "zwiebeln"
    assert normalize_de("fein gehackte Petersilie") == "petersilie"
    assert normalize_de("grob gemahlener Pfeffer") == "pfeffer"


def test_keeps_variety_and_colour_words():
    # colour/variety are NOT qualifiers and must remain (rote Zwiebel != Zwiebel)
    assert normalize_de("Rote Zwiebel") == "rote zwiebel"


def test_drops_parentheticals():
    assert normalize_de("Sahne (süß)") == "sahne"


def test_all_qualifiers_keeps_original():
    # if everything is a qualifier we don't end up empty
    assert normalize_de("frisch") == "frisch"


def test_fold_umlauts():
    assert fold_umlauts("Grünkohl") == "Gruenkohl"
    assert fold_umlauts("Weiße Soße") == "Weisse Sosse"


def test_helpers_are_pure():
    assert tokens("A B") == ["a", "b"]
    assert strip_qualifiers(["frische", "zwiebel"]) == ["zwiebel"]
