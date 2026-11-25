"""Vector store abstraction (SQLite+NumPy default, Qdrant optional) with metadata filtering."""

from __future__ import annotations

import json

import numpy as np

from app.db.database import Database


class SQLiteVectorStore:
    """Zero-dependency vector store backed by SQLite chunks table."""

    def __init__(self, db: Database):
        self.db = db

    def fetch_approved_chunks(
        self,
        crop: str | None = None,
        region: str | None = None,
    ) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, c.doc_id, c.text, c.embedding_json, c.metadata_json
                FROM chunks c
                JOIN documents d ON c.doc_id = d.doc_id
                WHERE d.approval_status = 'approved'
                """
            ).fetchall()

        results: list[dict] = []
        for r in rows:
            meta = json.loads(r["metadata_json"])
            doc_crop = (meta.get("crop") or "").lower()
            doc_region = (meta.get("region") or "").lower()

            if crop and doc_crop and doc_crop not in ("all", crop.lower()):
                continue
            if region and doc_region and doc_region not in ("all india", "all", region.lower()):
                continue

            results.append(
                {
                    "chunk_id": r["chunk_id"],
                    "doc_id": r["doc_id"],
                    "text": r["text"],
                    "embedding": np.array(json.loads(r["embedding_json"]), dtype=np.float32),
                    "metadata": meta,
                }
            )
        return results

    def dense_search(
        self,
        query_vec: list[float],
        top_k: int = 10,
        crop: str | None = None,
        region: str | None = None,
    ) -> list[tuple[dict, float]]:
        chunks = self.fetch_approved_chunks(crop=crop, region=region)
        # Relax region/crop filter if strict filter yields zero chunks
        if not chunks and (crop or region):
            chunks = self.fetch_approved_chunks(crop=crop, region=None)
        if not chunks and crop:
            chunks = self.fetch_approved_chunks(crop=None, region=None)

        if not chunks:
            return []

        q = np.array(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm > 1e-8:
            q = q / q_norm

        scored: list[tuple[dict, float]] = []
        for ch in chunks:
            emb = ch["embedding"]
            score = float(np.dot(q, emb))
            scored.append((ch, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
