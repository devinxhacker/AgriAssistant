"""Shared Pydantic models across all pipeline modules."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Language(str, Enum):
    HINDI = "hi"
    MARATHI = "mr"
    ENGLISH = "en"


class Intent(str, Enum):
    CROP_ADVICE = "crop_advice"
    PEST_DISEASE = "pest_disease"
    SCHEME_INFO = "scheme_info"
    MARKET_PRICE = "market_price"
    WEATHER = "weather"
    GREETING = "greeting"
    OUT_OF_SCOPE = "out_of_scope"


class GateDecision(str, Enum):
    ANSWER = "answer"
    ASK_REPEAT = "ask_repeat"
    REFUSE = "refuse"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ASRResult(BaseModel):
    transcript: str
    detected_language: str
    confidence: float = Field(ge=0.0, le=1.0)
    duration_sec: float = 0.0
    speech_ratio: float = 1.0
    provider: str = "unknown"


class ExtractedEntities(BaseModel):
    crop: str | None = None
    location: str | None = None
    state: str | None = None
    season: str | None = None
    commodity: str | None = None
    mandi: str | None = None
    scheme_name: str | None = None


class QueryUnderstandingResult(BaseModel):
    original_text: str
    detected_language: str
    is_code_mixed: bool = False
    intent: Intent
    entities: ExtractedEntities
    normalized_query: str


class DocumentMetadata(BaseModel):
    source: str
    publisher: str
    crop: str | None = None
    region: str | None = None
    season: str | None = None
    language: str = "en"
    publication_date: str
    version: str = "1.0"
    licence: str = "Public / Government Advisory"
    approval_status: ApprovalStatus = ApprovalStatus.PENDING


class RetrievedPassage(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    score: float
    rerank_score: float
    metadata: dict[str, Any]


class LiveToolResult(BaseModel):
    tool_name: str
    success: bool
    data_as_of: str
    source_name: str
    summary_en: str
    raw_data: dict[str, Any] = Field(default_factory=dict)


class ConfidenceResult(BaseModel):
    decision: GateDecision
    reason_code: str
    combined_score: float
    has_chemical_advice: bool = False
    safety_note_required: bool = False


class AssistantResponse(BaseModel):
    interaction_id: str
    language: str
    transcript: str
    intent: Intent
    entities: ExtractedEntities
    decision: GateDecision
    reason_code: str
    answer_text: str
    answer_english: str
    sources: list[str] = Field(default_factory=list)
    data_as_of: str | None = None
    audio_url: str | None = None
    audio_duration_sec: float | None = None
    latency_ms: int
    confidence: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackRequest(BaseModel):
    interaction_id: str
    rating: int = Field(ge=-1, le=1, description="1 for thumbs up, -1 for thumbs down")
    comment: str | None = None


class ReviewCorrectionRequest(BaseModel):
    interaction_id: str
    corrected_answer: str
    reviewer_name: str
    promote_to_eval: bool = False
