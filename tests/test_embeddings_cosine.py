"""Cosine / cache-invalidation tests with a stubbed embedder (no model download)."""
import numpy as np

from importer.services.embeddings import FoodEmbeddingIndex


class _Food:
    def __init__(self, id, name, plural="", aliases=None):
        self.id = id
        self.name = name
        self.plural = plural
        self.aliases = aliases or []


_VEC = {
    "saure sahne": [1.0, 0.0, 0.0],
    "schmand": [0.95, 0.1, 0.0],
    "zwiebel": [0.0, 1.0, 0.0],
    "zucker": [0.0, 0.0, 1.0],
}


def _fake_vec(text):
    t = text.lower()
    for key, vec in _VEC.items():
        if key in t:
            return np.asarray(vec, dtype=np.float32)
    return np.asarray([0.01, 0.01, 0.01], dtype=np.float32)


def _make_index(tmp_path):
    idx = FoodEmbeddingIndex(tmp_path / "emb.json", enabled=True)
    idx._enabled = True  # force on despite fastembed possibly absent
    return idx


def test_shortlist_orders_by_semantic_distance(tmp_path):
    idx = _make_index(tmp_path)
    idx._embed = lambda texts, prefix: [_fake_vec(t) for t in texts]
    foods = [_Food("1", "Saure Sahne"), _Food("2", "Zwiebel", "Zwiebeln"), _Food("3", "Zucker")]
    idx.build_or_update(foods)

    result = idx.shortlist("Schmand", k=2)
    ids = [fid for fid, _ in result]
    assert ids[0] == "1"  # nearest to Saure Sahne, not Zucker
    assert "3" not in ids


def test_cache_only_recomputes_changed_foods(tmp_path):
    foods = [_Food("1", "Saure Sahne"), _Food("2", "Zwiebel")]

    idx = _make_index(tmp_path)
    idx._embed = lambda texts, prefix: [_fake_vec(t) for t in texts]
    idx.build_or_update(foods)

    calls = {"n": 0}

    def counting(texts, prefix):
        calls["n"] += len(texts)
        return [_fake_vec(t) for t in texts]

    idx2 = _make_index(tmp_path)
    idx2._embed = counting
    idx2.build_or_update(foods)
    assert calls["n"] == 0  # unchanged -> nothing re-embedded

    calls["n"] = 0
    idx2.build_or_update(foods + [_Food("3", "Zucker")])
    assert calls["n"] == 1  # only the new food


def test_disabled_returns_empty(tmp_path):
    idx = FoodEmbeddingIndex(tmp_path / "x.json", enabled=False)
    assert idx.available is False
    assert idx.shortlist("Schmand") == []
