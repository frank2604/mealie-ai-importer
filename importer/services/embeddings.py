"""Local semantic embedding index for Mealie foods.

Why this exists: matching a recipe ingredient ("Schmand") to an existing Mealie
food is a *semantic* problem, not a character-similarity one. We compute a small
vector ("embedding") per food once, cache it, and at match time find the few
nearest foods by cosine similarity. Those few candidates are then handed to the
LLM for the final decision — far more accurate, cheaper, and constant-cost as the
Mealie database grows.

Runs fully locally via fastembed (ONNX, CPU, no PyTorch). If fastembed is not
installed the index reports ``available == False`` and callers fall back to the
LLM-over-the-full-list path, so nothing breaks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

try:  # optional heavy dependency
    from fastembed import TextEmbedding
except Exception:  # pragma: no cover - import guard
    TextEmbedding = None  # type: ignore

from .text_norm import normalize_de

logger = logging.getLogger("Embeddings")

# A multilingual paraphrase model (~1 GB, dim 768). Chosen over the smaller
# MiniLM variant because it recalls the hard German synonym/compound cases
# (Schmand→Saure Sahne, Weizenmehl→Mehl) markedly better, which is the whole
# point of the index. It is a *similarity* model (no e5-style task prefixes).
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
# This model does not use task prefixes; kept as constants so a future e5-style
# model can re-enable them in one place.
_QUERY_PREFIX = ""
_PASSAGE_PREFIX = ""


class FoodEmbeddingIndex:
    """Cosine-similarity shortlist over Mealie foods, backed by a JSON vector cache."""

    def __init__(
        self,
        cache_path: Path,
        *,
        enabled: bool = True,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        self._cache_path = Path(cache_path)
        self._model_name = model_name
        self._enabled = bool(enabled) and TextEmbedding is not None
        if enabled and TextEmbedding is None:
            logger.info("fastembed ist nicht installiert – semantisches Matching ist deaktiviert")
        self._model: Any = None
        # food_id -> {"hash": str, "vec": list[float]}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ids: List[str] = []
        self._matrix: Optional[np.ndarray] = None  # row-normalized (n, d)
        self._load_cache()

    @property
    def available(self) -> bool:
        return self._enabled

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _load_cache(self) -> None:
        if not self._cache_path.exists():
            return
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("Embeddings-Cache unlesbar, ignoriere")
            return
        if isinstance(data, dict):
            vectors = data.get("vectors")
            if isinstance(vectors, dict):
                # Drop vectors from a different model to avoid mixing spaces.
                if data.get("model") in (None, self._model_name):
                    self._cache = vectors

    def _save_cache(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"model": self._model_name, "vectors": self._cache}
            self._cache_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover - best effort
            logger.warning("Konnte Embeddings-Cache nicht schreiben: %s", exc)

    # ------------------------------------------------------------------
    # Model / embedding
    # ------------------------------------------------------------------
    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        kwargs: Dict[str, Any] = {}
        cache_dir = os.getenv("FASTEMBED_CACHE_PATH")
        if cache_dir:
            kwargs["cache_dir"] = cache_dir
        self._model = TextEmbedding(model_name=self._model_name, **kwargs)

    def _embed(self, texts: List[str], *, prefix: str) -> List[np.ndarray]:
        self._ensure_model()
        prefixed = [f"{prefix}{t}" for t in texts]
        return [np.asarray(vec, dtype=np.float32) for vec in self._model.embed(prefixed)]

    @staticmethod
    def _content(name: str, plural: str, aliases: Iterable[str]) -> str:
        parts = [name or "", plural or "", *[a for a in (aliases or []) if a]]
        normalized = [normalize_de(p) for p in parts if p]
        # de-duplicate while preserving order
        seen: List[str] = []
        for value in normalized:
            if value and value not in seen:
                seen.append(value)
        return " ".join(seen).strip()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------
    def build_or_update(self, foods: Iterable[Any]) -> None:
        """(Re)build the index from food candidates.

        Each *food* must expose ``id``, ``name``, ``plural`` and ``aliases``.
        Only new or content-changed foods are (re)embedded; removed ids are
        pruned. This means foods created directly in Mealie are picked up
        automatically on the next run.
        """
        if not self.available:
            return

        items: List[Tuple[str, str]] = []
        for food in foods:
            fid = str(getattr(food, "id", "") or "")
            if not fid:
                continue
            content = self._content(
                getattr(food, "name", ""),
                getattr(food, "plural", ""),
                getattr(food, "aliases", []) or [],
            )
            items.append((fid, content))

        present_ids = {fid for fid, _ in items}
        for fid in list(self._cache.keys()):
            if fid not in present_ids:
                del self._cache[fid]

        to_embed: List[Tuple[str, str, str]] = []
        for fid, content in items:
            digest = hashlib.sha1(content.encode("utf-8")).hexdigest()
            cached = self._cache.get(fid)
            if not cached or cached.get("hash") != digest or not cached.get("vec"):
                to_embed.append((fid, content, digest))

        if to_embed:
            logger.info("Berechne Embeddings für %s neue/geänderte Lebensmittel", len(to_embed))
            try:
                vectors = self._embed([c for _, c, _ in to_embed], prefix=_PASSAGE_PREFIX)
            except Exception as exc:  # pragma: no cover - model/runtime failure
                logger.warning("Embedding-Berechnung fehlgeschlagen: %s – deaktiviere semantisches Matching", exc)
                self._enabled = False
                return
            for (fid, _content, digest), vec in zip(to_embed, vectors):
                self._cache[fid] = {"hash": digest, "vec": vec.tolist()}
            self._save_cache()

        self._rebuild_matrix()

    def _rebuild_matrix(self) -> None:
        ids: List[str] = []
        rows: List[List[float]] = []
        for fid, entry in self._cache.items():
            vec = entry.get("vec")
            if vec:
                ids.append(fid)
                rows.append(vec)
        if rows:
            matrix = np.asarray(rows, dtype=np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._matrix = matrix / norms
        else:
            self._matrix = None
        self._ids = ids

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def shortlist(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """Return up to *k* ``(food_id, cosine_score)`` for the closest foods."""
        if not self.available or self._matrix is None:
            return []
        normalized = normalize_de(query or "")
        if not normalized:
            return []
        try:
            qv = self._embed([normalized], prefix=_QUERY_PREFIX)[0]
        except Exception as exc:  # pragma: no cover - runtime safeguard
            logger.debug("Query-Embedding fehlgeschlagen: %s", exc)
            return []
        norm = float(np.linalg.norm(qv))
        if norm == 0.0:
            return []
        scores = self._matrix @ (qv / norm)
        k = max(1, min(k, len(self._ids)))
        order = np.argsort(-scores)[:k]
        return [(self._ids[i], float(scores[i])) for i in order]
