"""Multilingual embedding service (sentence-transformers or deterministic char-ngram projection)."""

from __future__ import annotations

import hashlib
import logging
import re

import numpy as np

from app.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Produces L2-normalized dense embeddings for multilingual agricultural text."""

    def __init__(self, settings: Settings, dim: int = 384):
        self.settings = settings
        self.dim = dim
        self._st_model = None

    def _get_st_model(self):
        if self._st_model is not None:
            return self._st_model
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._st_model = SentenceTransformer(self.settings.embedding_model)
        return self._st_model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.settings.embedding_provider in ("auto", "sentence_transformers"):
            try:
                model = self._get_st_model()
                vecs = model.encode(texts, normalize_embeddings=True)
                return [v.tolist() for v in vecs]
            except ImportError:
                logger.debug("sentence-transformers not installed; using char-ngram embeddings.")
            except Exception as exc:
                logger.warning("SentenceTransformer failed, falling back: %s", exc)

        return [self._hash_ngram_embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def _hash_ngram_embed(self, text: str) -> list[float]:
        """Fast, deterministic 384-d word + character trigram hashed projection."""
        vec = np.zeros(self.dim, dtype=np.float32)
        cleaned = re.sub(r"[^\w\u0900-\u097F\s]", " ", text.lower())
        words = cleaned.split()
        features: list[tuple[str, float]] = []

        for w in words:
            features.append((f"w:{w}", 2.0))
            padded = f"^{w}$"
            for i in range(max(1, len(padded) - 2)):
                features.append((f"c:{padded[i:i+3]}", 1.0))

        for feat, weight in features:
            digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vec[idx] += sign * weight

        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec /= norm
        return vec.tolist()
