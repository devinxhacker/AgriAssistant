"""Core user-facing API routes for text/voice queries, audio playback, feedback, and privacy."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel

from app.models.schemas import AssistantResponse, FeedbackRequest

router = APIRouter(tags=["assistant"])

QUERY_COUNTER = Counter(
    "agri_queries_total",
    "Total agricultural assistant queries",
    ["language", "intent", "decision"],
)
LATENCY_HIST = Histogram(
    "agri_query_latency_seconds",
    "End-to-end query latency in seconds",
)


class TextQueryRequest(BaseModel):
    text: str
    language: str | None = None
    phone_number: str | None = None
    synthesize_audio: bool = True


class ConsentRequest(BaseModel):
    phone_number: str
    granted: bool = True


@router.get("/health")
async def health_check(request: Request):
    db = request.app.state.db
    with db.connection() as conn:
        doc_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE approval_status = 'approved'"
        ).fetchone()[0]
    return {"status": "healthy", "approved_documents": doc_count}


@router.get("/metrics")
async def prometheus_metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"))


@router.post("/api/v1/query", response_model=AssistantResponse)
async def query_text(payload: TextQueryRequest, request: Request):
    pipeline = request.app.state.pipeline
    resp = await pipeline.process_text(
        text=payload.text,
        language_hint=payload.language,
        phone_number=payload.phone_number,
        channel="web_text",
        synthesize_audio=payload.synthesize_audio,
    )
    QUERY_COUNTER.labels(resp.language, resp.intent.value, resp.decision.value).inc()
    LATENCY_HIST.observe(resp.latency_ms / 1000.0)
    return resp


@router.post("/api/v1/voice", response_model=AssistantResponse)
async def query_voice(
    request: Request,
    audio: UploadFile = File(...),
    language: str | None = Form(default=None),
    transcript_hint: str | None = Form(default=None),
    phone_number: str | None = Form(default=None),
):
    pipeline = request.app.state.pipeline
    settings = request.app.state.settings
    suffix = Path(audio.filename or "voice.wav").suffix or ".wav"
    temp_path = settings.audio_storage_dir / f"in_{uuid.uuid4().hex[:10]}{suffix}"
    temp_path.write_bytes(await audio.read())

    resp = await pipeline.process_voice(
        audio_path=temp_path,
        language_hint=language,
        transcript_hint=transcript_hint,
        phone_number=phone_number,
        channel="web_voice",
    )
    QUERY_COUNTER.labels(resp.language, resp.intent.value, resp.decision.value).inc()
    LATENCY_HIST.observe(resp.latency_ms / 1000.0)
    return resp


@router.get("/api/v1/audio/{filename}")
async def serve_audio(filename: str, request: Request):
    settings = request.app.state.settings
    safe_name = Path(filename).name
    target = settings.audio_storage_dir / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    media_type = "audio/ogg" if target.suffix == ".ogg" else "audio/wav"
    return FileResponse(target, media_type=media_type)


@router.post("/api/v1/feedback")
async def submit_feedback(payload: FeedbackRequest, request: Request):
    db = request.app.state.db
    with db.connection() as conn:
        cur = conn.execute(
            "UPDATE interactions SET feedback_rating = ?, feedback_comment = ? WHERE interaction_id = ?",
            (payload.rating, payload.comment, payload.interaction_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Interaction not found")
    return {"status": "recorded", "interaction_id": payload.interaction_id}


@router.post("/api/v1/privacy/consent")
async def record_consent(payload: ConsentRequest, request: Request):
    pipeline = request.app.state.pipeline
    pipeline.privacy.record_consent(payload.phone_number, payload.granted)
    return {"status": "updated", "granted": payload.granted}


@router.delete("/api/v1/privacy/user/{phone_hash}")
async def delete_user_data(phone_hash: str, request: Request):
    pipeline = request.app.state.pipeline
    return pipeline.privacy.delete_user_data(phone_hash)
