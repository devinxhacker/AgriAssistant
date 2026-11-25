"""Hybrid retrieval engine: Dense + BM25 + Reciprocal Rank Fusion (RRF) + Reranker."""

from __future__ import annotations

import logging

from app.config import Settings
from app.models.schemas import RetrievedPassage
from app.retrieval.bm25 import BM25Index, tokenize
from app.retrieval.embeddings import EmbeddingService
from app.retrieval.vector_store import SQLiteVectorStore

logger = logging.getLogger(__name__)

STOPWORDS = {
    "the", "is", "are", "in", "on", "of", "for", "to", "a", "an", "and", "or",
    "what", "how", "when", "which", "my", "can", "i", "do", "with", "about",
}


class HybridRetriever:
    """Combines dense cosine search and BM25 using RRF, then reranks candidates."""

    def __init__(
        self,
        settings: Settings,
        embeddings: EmbeddingService,
        vector_store: SQLiteVectorStore,
    ):
        self.settings = settings
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.bm25 = BM25Index()

    def retrieve(
        self,
        query_en: str,
        top_k: int = 5,
        crop: str | None = None,
        region: str | None = None,
    ) -> list[RetrievedPassage]:
        chunks = self.vector_store.fetch_approved_chunks(crop=crop, region=region)
        if not chunks and (crop or region):
            chunks = self.vector_store.fetch_approved_chunks(crop=crop, region=None)
        if not chunks:
            chunks = self.vector_store.fetch_approved_chunks(crop=None, region=None)
        if not chunks:
            return []

        chunk_map = {c["chunk_id"]: c for c in chunks}

        # 1. Dense search
        q_vec = self.embeddings.embed_query(query_en)
        dense_hits = self.vector_store.dense_search(
            q_vec, top_k=max(10, top_k * 3), crop=crop, region=region
        )

        # 2. BM25 sparse search
        self.bm25.build([(c["chunk_id"], c["text"]) for c in chunks])
        bm25_hits = self.bm25.search(query_en, top_k=max(10, top_k * 3))

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_k = 60.0
        rrf_scores: dict[str, float] = {}
        dense_sim: dict[str, float] = {}

        for rank, (ch, score) in enumerate(dense_hits, start=1):
            cid = ch["chunk_id"]
            dense_sim[cid] = score
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)

        for rank, (cid, _bm25_score) in enumerate(bm25_hits, start=1):
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)

        if not rrf_scores:
            return []

        ranked_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)
        candidates = [chunk_map[cid] for cid in ranked_ids[: max(8, top_k * 2)]]

        # 4. Reranking (lexical-semantic calibrated reranker)
        passages: list[RetrievedPassage] = []
        q_terms = {t for t in tokenize(query_en) if t not in STOPWORDS and len(t) > 1}

        for ch in candidates:
            cid = ch["chunk_id"]
            c_terms = set(tokenize(ch["text"]))
            overlap = len(q_terms & c_terms) / max(1, len(q_terms))
            d_score = max(0.0, dense_sim.get(cid, 0.0))
            meta = ch["metadata"]

            # Boost exact crop/region metadata match
            meta_boost = 0.0
            if crop and (meta.get("crop") or "").lower() == crop.lower():
                meta_boost += 0.12
            if region and (meta.get("region") or "").lower() == region.lower():
                meta_boost += 0.08

            rerank_score = min(1.0, 0.55 * overlap + 0.35 * d_score + meta_boost)
            passages.append(
                RetrievedPassage(
                    chunk_id=cid,
                    doc_id=ch["doc_id"],
                    text=ch["text"],
                    score=round(rrf_scores[cid], 4),
                    rerank_score=round(rerank_score, 4),
                    metadata=meta,
                )
            )

        passages.sort(key=lambda p: p.rerank_score, reverse=True)
        return passages[:top_k]
