"""Structure-aware chunking, duplicate detection, versioning, and KB ingestion."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from app.db.database import Database
from app.knowledge.cleaner import clean_text, extract_text_from_file
from app.models.schemas import ApprovalStatus, DocumentMetadata
from app.retrieval.embeddings import EmbeddingService


def chunk_markdown_structured(text: str, max_chars: int = 650, overlap_chars: int = 80) -> list[str]:
    """Split text along heading/paragraph boundaries while preserving section headers."""
    sections = re.split(r"\n(?=#{1,3}\s)", text)
    chunks: list[str] = []

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        heading = lines[0] if lines and lines[0].startswith("#") else ""
        if len(sec) <= max_chars:
            chunks.append(sec)
            continue

        paragraphs = sec.split("\n\n")
        current = ""
        for para in paragraphs:
            candidate = f"{current}\n\n{para}".strip() if current else para
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                prefix = f"{heading}\n" if heading and not para.startswith("#") else ""
                if len(para) > max_chars:
                    start = 0
                    while start < len(para):
                        part = para[start : start + max_chars]
                        chunks.append(f"{prefix}{part}".strip())
                        start += max(1, max_chars - overlap_chars)
                    current = ""
                else:
                    current = f"{prefix}{para}".strip()
        if current:
            chunks.append(current)

    return [c for c in chunks if len(c.strip()) > 20]


class KnowledgeIngestor:
    """Handles document ingestion, deduplication, versioning, and approval state."""

    def __init__(self, db: Database, embeddings: EmbeddingService):
        self.db = db
        self.embeddings = embeddings

    @staticmethod
    def compute_hash(text: str) -> str:
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def ingest_text(
        self,
        title: str,
        raw_text: str,
        metadata: DocumentMetadata,
    ) -> dict:
        cleaned = clean_text(raw_text)
        content_hash = self.compute_hash(cleaned)

        with self.db.connection() as conn:
            existing = conn.execute(
                "SELECT doc_id, version, approval_status FROM documents WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
            if existing:
                return {
                    "status": "duplicate_skipped",
                    "doc_id": existing["doc_id"],
                    "version": existing["version"],
                    "approval_status": existing["approval_status"],
                }

            doc_id = f"doc_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO documents (
                    doc_id, title, content_hash, source, publisher, crop, region,
                    season, language, publication_date, version, licence, approval_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    title,
                    content_hash,
                    metadata.source,
                    metadata.publisher,
                    metadata.crop.lower() if metadata.crop else None,
                    metadata.region,
                    metadata.season,
                    metadata.language,
                    metadata.publication_date,
                    metadata.version,
                    metadata.licence,
                    metadata.approval_status.value,
                ),
            )

            chunks = chunk_markdown_structured(cleaned)
            vectors = self.embeddings.embed_batch(chunks) if chunks else []
            meta_dict = metadata.model_dump(mode="json")
            meta_dict["title"] = title

            for idx, (chunk_text, vec) in enumerate(zip(chunks, vectors)):
                chunk_id = f"{doc_id}_c{idx:03d}"
                conn.execute(
                    """
                    INSERT INTO chunks (chunk_id, doc_id, chunk_index, text, embedding_json, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        doc_id,
                        idx,
                        chunk_text,
                        json.dumps(vec),
                        json.dumps(meta_dict, ensure_ascii=False),
                    ),
                )

        return {
            "status": "ingested",
            "doc_id": doc_id,
            "chunks_created": len(chunks),
            "approval_status": metadata.approval_status.value,
        }

    def ingest_file(self, file_path: Path, title: str, metadata: DocumentMetadata) -> dict:
        text = extract_text_from_file(file_path)
        return self.ingest_text(title=title, raw_text=text, metadata=metadata)

    def set_approval_status(self, doc_id: str, status: ApprovalStatus) -> bool:
        with self.db.connection() as conn:
            cur = conn.execute(
                "UPDATE documents SET approval_status = ? WHERE doc_id = ?",
                (status.value, doc_id),
            )
            if cur.rowcount == 0:
                return False
            rows = conn.execute(
                "SELECT chunk_id, metadata_json FROM chunks WHERE doc_id = ?", (doc_id,)
            ).fetchall()
            for r in rows:
                meta = json.loads(r["metadata_json"])
                meta["approval_status"] = status.value
                conn.execute(
                    "UPDATE chunks SET metadata_json = ? WHERE chunk_id = ?",
                    (json.dumps(meta, ensure_ascii=False), r["chunk_id"]),
                )
        return True

    def list_documents(self) -> list[dict]:
        with self.db.connection() as conn:
            rows = conn.execute(
                """
                SELECT d.*, COUNT(c.chunk_id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON d.doc_id = c.doc_id
                GROUP BY d.doc_id
                ORDER BY d.created_at DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]
