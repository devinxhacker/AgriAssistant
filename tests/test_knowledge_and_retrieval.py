"""Tests for knowledge ingestion, deduplication, approval gating, and hybrid retrieval."""

from app.knowledge.ingestor import KnowledgeIngestor
from app.models.schemas import ApprovalStatus, DocumentMetadata


def test_dedup_and_approval_gating(seeded_pipeline):
    ingestor = KnowledgeIngestor(seeded_pipeline.db, seeded_pipeline.embeddings)
    meta = DocumentMetadata(
        source="Unverified Blog",
        publisher="Unknown",
        crop="cotton",
        region="Maharashtra",
        publication_date="2026-11-01",
        approval_status=ApprovalStatus.PENDING,
    )
    res1 = ingestor.ingest_text(
        title="Draft Unapproved Note",
        raw_text="Unverified secret chemical xyz-999 spray 50 ml per liter on cotton.",
        metadata=meta,
    )
    assert res1["status"] == "ingested"

    # Duplicate should be skipped
    res2 = ingestor.ingest_text(
        title="Draft Unapproved Note",
        raw_text="Unverified secret chemical xyz-999 spray 50 ml per liter on cotton.",
        metadata=meta,
    )
    assert res2["status"] == "duplicate_skipped"

    # Pending document must NOT appear in retrieval results
    passages = seeded_pipeline.retriever.retrieve("xyz-999 secret chemical cotton", top_k=5)
    assert all("xyz-999" not in p.text for p in passages)


def test_hybrid_retrieval_finds_approved_cotton_advisory(seeded_pipeline):
    passages = seeded_pipeline.retriever.retrieve(
        "yellowing leaves on cotton nitrogen deficiency",
        top_k=3,
        crop="cotton",
        region="Maharashtra",
    )
    assert len(passages) >= 1
    assert "CICR" in passages[0].metadata.get("source", "")
