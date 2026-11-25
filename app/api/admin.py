"""Admin console and expert review loop API routes with role-based access control."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.eval.runner import run_evaluation
from app.knowledge.ingestor import KnowledgeIngestor
from app.models.schemas import ApprovalStatus, DocumentMetadata, ReviewCorrectionRequest

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ALLOWED_ROLES = {"admin", "reviewer", "analyst"}


def require_role(role: str, required: set[str]) -> None:
    if role not in required:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' is not authorized. Required: {sorted(required)}",
        )


class IngestTextRequest(BaseModel):
    title: str
    content: str
    source: str
    publisher: str
    crop: str | None = None
    region: str | None = None
    season: str | None = None
    language: str = "en"
    publication_date: str = "2026-11-01"
    version: str = "1.0"
    licence: str = "Public Government Advisory"
    approval_status: ApprovalStatus = ApprovalStatus.PENDING


class GlossaryTermRequest(BaseModel):
    category: str
    en: str
    hi: str
    mr: str
    notes: str = ""


@router.get("/documents")
async def list_documents(
    request: Request,
    x_admin_role: str = Header(default="analyst"),
):
    require_role(x_admin_role, ALLOWED_ROLES)
    ingestor = KnowledgeIngestor(request.app.state.db, request.app.state.pipeline.embeddings)
    return {"documents": ingestor.list_documents()}


@router.post("/documents/ingest-text")
async def ingest_text_doc(
    payload: IngestTextRequest,
    request: Request,
    x_admin_role: str = Header(default="admin"),
):
    require_role(x_admin_role, {"admin", "reviewer"})
    ingestor = KnowledgeIngestor(request.app.state.db, request.app.state.pipeline.embeddings)
    meta = DocumentMetadata(
        source=payload.source,
        publisher=payload.publisher,
        crop=payload.crop,
        region=payload.region,
        season=payload.season,
        language=payload.language,
        publication_date=payload.publication_date,
        version=payload.version,
        licence=payload.licence,
        approval_status=payload.approval_status,
    )
    return ingestor.ingest_text(title=payload.title, raw_text=payload.content, metadata=meta)


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    source: str = Form(...),
    publisher: str = Form(...),
    crop: str | None = Form(default=None),
    region: str | None = Form(default=None),
    publication_date: str = Form(default="2026-11-01"),
    x_admin_role: str = Header(default="admin"),
):
    require_role(x_admin_role, {"admin", "reviewer"})
    settings = request.app.state.settings
    dest = settings.audio_storage_dir.parent / "uploads" / f"{uuid.uuid4().hex[:8]}_{Path(file.filename or 'doc.txt').name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())

    ingestor = KnowledgeIngestor(request.app.state.db, request.app.state.pipeline.embeddings)
    meta = DocumentMetadata(
        source=source,
        publisher=publisher,
        crop=crop,
        region=region,
        publication_date=publication_date,
        approval_status=ApprovalStatus.PENDING,
    )
    return ingestor.ingest_file(dest, title=title, metadata=meta)


@router.post("/documents/{doc_id}/approval")
async def update_approval(
    doc_id: str,
    status: ApprovalStatus,
    request: Request,
    x_admin_role: str = Header(default="reviewer"),
):
    require_role(x_admin_role, {"admin", "reviewer"})
    ingestor = KnowledgeIngestor(request.app.state.db, request.app.state.pipeline.embeddings)
    ok = ingestor.set_approval_status(doc_id, status)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"doc_id": doc_id, "approval_status": status.value}


@router.get("/glossary")
async def get_glossary(
    request: Request,
    x_admin_role: str = Header(default="analyst"),
):
    require_role(x_admin_role, ALLOWED_ROLES)
    with request.app.state.db.connection() as conn:
        rows = conn.execute("SELECT * FROM glossary_terms ORDER BY category, en").fetchall()
    return {"terms": [dict(r) for r in rows]}


@router.post("/glossary")
async def add_glossary_term(
    payload: GlossaryTermRequest,
    request: Request,
    x_admin_role: str = Header(default="admin"),
):
    require_role(x_admin_role, {"admin", "reviewer"})
    term_id = f"term_{uuid.uuid4().hex[:8]}"
    with request.app.state.db.connection() as conn:
        conn.execute(
            "INSERT INTO glossary_terms (term_id, category, en, hi, mr, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (term_id, payload.category, payload.en, payload.hi, payload.mr, payload.notes),
        )
        rows = conn.execute("SELECT * FROM glossary_terms").fetchall()
    request.app.state.pipeline.translator.reload_glossary([dict(r) for r in rows])
    return {"status": "added", "term_id": term_id}


@router.get("/review-queue")
async def list_review_queue(
    request: Request,
    x_admin_role: str = Header(default="reviewer"),
):
    require_role(x_admin_role, ALLOWED_ROLES)
    with request.app.state.db.connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM interactions
            WHERE decision != 'answer' OR confidence < 0.70 OR feedback_rating = -1
            ORDER BY created_at DESC
            LIMIT 50
            """
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.post("/review-queue/correct")
async def submit_review_correction(
    payload: ReviewCorrectionRequest,
    request: Request,
    x_admin_role: str = Header(default="reviewer"),
):
    require_role(x_admin_role, {"admin", "reviewer"})
    with request.app.state.db.connection() as conn:
        row = conn.execute(
            "SELECT transcript, language FROM interactions WHERE interaction_id = ?",
            (payload.interaction_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Interaction not found")
        conn.execute(
            "UPDATE interactions SET reviewed_by = ?, corrected_answer = ? WHERE interaction_id = ?",
            (payload.reviewer_name, payload.corrected_answer, payload.interaction_id),
        )

    if payload.promote_to_eval:
        eval_path = Path("data/eval_set.json")
        cases = json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.exists() else []
        cases.append(
            {
                "id": f"review_{payload.interaction_id}",
                "language": row["language"],
                "query": row["transcript"],
                "expected_decision": "answer",
                "reference_translation_en": payload.corrected_answer,
            }
        )
        eval_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"status": "saved", "promoted_to_eval": payload.promote_to_eval}


@router.get("/interactions/summary")
async def interaction_summary(
    request: Request,
    x_admin_role: str = Header(default="analyst"),
):
    require_role(x_admin_role, ALLOWED_ROLES)
    with request.app.state.db.connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        by_decision = conn.execute(
            "SELECT decision, COUNT(*) AS cnt FROM interactions GROUP BY decision"
        ).fetchall()
        by_lang = conn.execute(
            "SELECT language, COUNT(*) AS cnt FROM interactions GROUP BY language"
        ).fetchall()
        avg_lat = conn.execute("SELECT AVG(latency_ms) FROM interactions").fetchone()[0] or 0
    return {
        "total_interactions": total,
        "avg_latency_ms": round(float(avg_lat), 1),
        "by_decision": {r["decision"]: r["cnt"] for r in by_decision},
        "by_language": {r["language"]: r["cnt"] for r in by_lang},
    }


@router.post("/eval/run")
async def trigger_evaluation(
    request: Request,
    x_admin_role: str = Header(default="analyst"),
):
    require_role(x_admin_role, ALLOWED_ROLES)
    return await run_evaluation(request.app.state.pipeline)
