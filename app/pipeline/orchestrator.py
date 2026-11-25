"""End-to-end agricultural assistant pipeline orchestrator."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from app.config import Settings
from app.db.database import Database
from app.db.privacy import PrivacyManager, hash_phone
from app.generation.generator import GroundedAnswerGenerator
from app.models.schemas import (
    ASRResult,
    AssistantResponse,
    GateDecision,
    Intent,
    LiveToolResult,
    RetrievedPassage,
)
from app.nlp.query_understanding import QueryUnderstandingService
from app.nlp.translation import TranslationService
from app.retrieval.embeddings import EmbeddingService
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.vector_store import SQLiteVectorStore
from app.safety.confidence_gate import ConfidenceGate
from app.safety.guardrails import check_content_safety
from app.speech.asr import ASRService
from app.speech.tts import TTSService
from app.tools.mandi import MandiPriceTool
from app.tools.weather import WeatherTool

GREETING_TEXT = {
    "en": "Namaste! I am AgriAssistant. Ask me about crops, pests, mandi prices, weather, or government schemes.",
    "hi": "नमस्ते! मैं एग्रीअसिस्टेंट हूँ। आप मुझसे फसल, कीट-रोग, मंडी भाव, मौसम या सरकारी योजनाओं के बारे में पूछ सकते हैं।",
    "mr": "नमस्कार! मी अ‍ॅग्रीअसिस्टंट आहे. तुम्ही मला पीक, कीड-रोग, बाजार भाव, हवामान किंवा सरकारी योजनांबद्दल विचारू शकता.",
}


class AgriPipeline:
    """Coordinates all 14 modules from audio/text input to spoken & cited response."""

    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self.privacy = PrivacyManager(db, settings.audio_storage_dir, settings.audio_retention_hours)
        self.asr = ASRService(settings)
        self.tts = TTSService(settings)
        self.nlu = QueryUnderstandingService()
        self.translator = TranslationService(settings)
        self.embeddings = EmbeddingService(settings)
        self.vector_store = SQLiteVectorStore(db)
        self.retriever = HybridRetriever(settings, self.embeddings, self.vector_store)
        self.mandi_tool = MandiPriceTool(settings)
        self.weather_tool = WeatherTool(settings)
        self.generator = GroundedAnswerGenerator(settings)
        self.gate = ConfidenceGate(settings)

    async def process_voice(
        self,
        audio_path: Path,
        language_hint: str | None = None,
        transcript_hint: str | None = None,
        phone_number: str | None = None,
        channel: str = "voice_api",
    ) -> AssistantResponse:
        t0 = time.perf_counter()
        asr_res = await self.asr.transcribe(
            audio_path, language_hint=language_hint, transcript_hint=transcript_hint
        )
        return await self._run_core(
            transcript=asr_res.transcript,
            asr_res=asr_res,
            language_hint=language_hint or asr_res.detected_language,
            phone_number=phone_number,
            channel=channel,
            synthesize_audio=True,
            t0=t0,
        )

    async def process_text(
        self,
        text: str,
        language_hint: str | None = None,
        phone_number: str | None = None,
        channel: str = "text_api",
        synthesize_audio: bool = False,
    ) -> AssistantResponse:
        t0 = time.perf_counter()
        asr_res = ASRResult(
            transcript=text.strip(),
            detected_language=language_hint or "auto",
            confidence=1.0,
            provider="text_input",
        )
        return await self._run_core(
            transcript=text.strip(),
            asr_res=asr_res,
            language_hint=language_hint,
            phone_number=phone_number,
            channel=channel,
            synthesize_audio=synthesize_audio,
            t0=t0,
        )

    async def _run_core(
        self,
        transcript: str,
        asr_res: ASRResult,
        language_hint: str | None,
        phone_number: str | None,
        channel: str,
        synthesize_audio: bool,
        t0: float,
    ) -> AssistantResponse:
        interaction_id = f"int_{uuid.uuid4().hex[:12]}"
        p_hash = hash_phone(phone_number) if phone_number else None

        # Session context lookup
        session_region = None
        session_crop = None
        if phone_number:
            sess = self.privacy.get_or_create_session(phone_number)
            session_region = sess.get("last_region")
            session_crop = sess.get("last_crop")

        # Low ASR confidence short-circuit
        if asr_res.confidence < self.settings.asr_min_confidence or not transcript:
            lang = language_hint if language_hint in ("hi", "mr", "en") else "hi"
            nlu_empty = self.nlu.analyze(transcript or "", language_hint=lang)
            ans_text = self.gate.get_repeat_text(lang)
            return await self._finalize(
                interaction_id=interaction_id,
                p_hash=p_hash,
                channel=channel,
                lang=lang,
                transcript=transcript,
                intent=nlu_empty.intent,
                entities=nlu_empty.entities,
                decision=GateDecision.ASK_REPEAT,
                reason_code="LOW_ASR_CONFIDENCE",
                answer_text=ans_text,
                answer_en=self.gate.get_repeat_text("en"),
                sources=[],
                data_as_of=None,
                confidence=asr_res.confidence,
                synthesize_audio=synthesize_audio,
                t0=t0,
            )

        # Safety guardrail check
        is_safe, safety_code = check_content_safety(transcript)
        nlu_res = self.nlu.analyze(transcript, language_hint=language_hint)
        lang = nlu_res.detected_language

        if not is_safe:
            ans_text = self.gate.get_refusal_text(lang)
            return await self._finalize(
                interaction_id=interaction_id,
                p_hash=p_hash,
                channel=channel,
                lang=lang,
                transcript=transcript,
                intent=Intent.OUT_OF_SCOPE,
                entities=nlu_res.entities,
                decision=GateDecision.REFUSE,
                reason_code=safety_code,
                answer_text=ans_text,
                answer_en=self.gate.get_refusal_text("en"),
                sources=[],
                data_as_of=None,
                confidence=0.0,
                synthesize_audio=synthesize_audio,
                t0=t0,
            )

        # Update session context if entities detected
        if phone_number:
            self.privacy.update_session_context(
                phone_number,
                language_pref=lang,
                last_region=nlu_res.entities.state or nlu_res.entities.location,
                last_crop=nlu_res.entities.crop,
            )

        crop = nlu_res.entities.crop or session_crop
        region = nlu_res.entities.state or session_region
        location = nlu_res.entities.location or region

        # Greeting shortcut
        if nlu_res.intent == Intent.GREETING:
            ans_text = GREETING_TEXT.get(lang, GREETING_TEXT["en"])
            return await self._finalize(
                interaction_id=interaction_id,
                p_hash=p_hash,
                channel=channel,
                lang=lang,
                transcript=transcript,
                intent=nlu_res.intent,
                entities=nlu_res.entities,
                decision=GateDecision.ANSWER,
                reason_code="GREETING",
                answer_text=ans_text,
                answer_en=GREETING_TEXT["en"],
                sources=[],
                data_as_of=None,
                confidence=1.0,
                synthesize_audio=synthesize_audio,
                t0=t0,
            )

        # Translate query to English for retrieval/tools
        query_en = self.translator.to_english(nlu_res.normalized_query, lang)
        passages: list[RetrievedPassage] = []
        live_res: LiveToolResult | None = None
        sources: list[str] = []
        data_as_of: str | None = None

        if nlu_res.intent == Intent.MARKET_PRICE:
            live_res = await self.mandi_tool.get_price(
                commodity=crop,
                market=nlu_res.entities.mandi or location,
                state=region,
            )
            if live_res.success:
                sources = [live_res.source_name]
                data_as_of = live_res.data_as_of
        elif nlu_res.intent == Intent.WEATHER:
            live_res = await self.weather_tool.get_weather(location=location)
            if live_res.success:
                sources = [live_res.source_name]
                data_as_of = live_res.data_as_of
        elif nlu_res.intent != Intent.OUT_OF_SCOPE:
            passages = self.retriever.retrieve(
                query_en=query_en,
                top_k=5,
                crop=crop,
                region=region,
            )

        gate_res = self.gate.evaluate(
            asr_confidence=asr_res.confidence,
            intent=nlu_res.intent,
            passages=passages,
            live_result=live_res,
            query_text=query_en,
        )

        if gate_res.decision == GateDecision.REFUSE:
            ans_text = self.gate.get_refusal_text(lang)
            return await self._finalize(
                interaction_id=interaction_id,
                p_hash=p_hash,
                channel=channel,
                lang=lang,
                transcript=transcript,
                intent=nlu_res.intent,
                entities=nlu_res.entities,
                decision=GateDecision.REFUSE,
                reason_code=gate_res.reason_code,
                answer_text=ans_text,
                answer_en=self.gate.get_refusal_text("en"),
                sources=[],
                data_as_of=None,
                confidence=gate_res.combined_score,
                synthesize_audio=synthesize_audio,
                t0=t0,
            )

        # Generate grounded English answer
        if live_res and live_res.success:
            answer_en = live_res.summary_en
        else:
            answer_en, sources = await self.generator.generate_from_passages(query_en, passages)

        answer_local = self.translator.from_english(answer_en, lang)
        if gate_res.safety_note_required:
            answer_local = f"{answer_local} {self.gate.get_chemical_safety_note(lang)}"
            answer_en = f"{answer_en} {self.gate.get_chemical_safety_note('en')}"

        return await self._finalize(
            interaction_id=interaction_id,
            p_hash=p_hash,
            channel=channel,
            lang=lang,
            transcript=transcript,
            intent=nlu_res.intent,
            entities=nlu_res.entities,
            decision=gate_res.decision,
            reason_code=gate_res.reason_code,
            answer_text=answer_local,
            answer_en=answer_en,
            sources=sources,
            data_as_of=data_as_of,
            confidence=gate_res.combined_score,
            synthesize_audio=synthesize_audio,
            t0=t0,
        )

    async def _finalize(
        self,
        *,
        interaction_id: str,
        p_hash: str | None,
        channel: str,
        lang: str,
        transcript: str,
        intent: Intent,
        entities,
        decision: GateDecision,
        reason_code: str,
        answer_text: str,
        answer_en: str,
        sources: list[str],
        data_as_of: str | None,
        confidence: float,
        synthesize_audio: bool,
        t0: float,
    ) -> AssistantResponse:
        audio_url: str | None = None
        audio_path_str: str | None = None
        audio_dur: float | None = None

        if synthesize_audio:
            stem = self.settings.audio_storage_dir / f"reply_{interaction_id}"
            out_path, audio_dur = await self.tts.synthesize(answer_text, lang, stem)
            audio_path_str = str(out_path)
            audio_url = f"/api/v1/audio/{out_path.name}"

        latency_ms = int((time.perf_counter() - t0) * 1000)

        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO interactions (
                    interaction_id, phone_hash, channel, language, transcript, intent,
                    entities_json, decision, reason_code, answer_text, answer_english,
                    sources_json, confidence, latency_ms, audio_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction_id,
                    p_hash,
                    channel,
                    lang,
                    transcript,
                    intent.value,
                    entities.model_dump_json(),
                    decision.value,
                    reason_code,
                    answer_text,
                    answer_en,
                    json.dumps(sources, ensure_ascii=False),
                    confidence,
                    latency_ms,
                    audio_path_str,
                ),
            )

        return AssistantResponse(
            interaction_id=interaction_id,
            language=lang,
            transcript=transcript,
            intent=intent,
            entities=entities,
            decision=decision,
            reason_code=reason_code,
            answer_text=answer_text,
            answer_english=answer_en,
            sources=sources,
            data_as_of=data_as_of,
            audio_url=audio_url,
            audio_duration_sec=audio_dur,
            latency_ms=latency_ms,
            confidence=confidence,
        )
