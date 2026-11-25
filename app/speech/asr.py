"""Speech-to-Text (ASR) service supporting Whisper, Bhashini, and acoustic fallback."""

from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.audio.processor import analyze_wav_vad, normalize_to_wav16k
from app.config import Settings
from app.models.schemas import ASRResult

logger = logging.getLogger(__name__)


class ASRService:
    """Unified ASR interface with VAD quality checks and per-utterance confidence."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._whisper_model = None

    def _load_whisper(self):
        if self._whisper_model is not None:
            return self._whisper_model
        from faster_whisper import WhisperModel  # type: ignore

        self._whisper_model = WhisperModel(
            self.settings.whisper_model_size,
            device="cpu",
            compute_type="int8",
        )
        return self._whisper_model

    async def transcribe(
        self,
        audio_path: Path,
        language_hint: str | None = None,
        transcript_hint: str | None = None,
    ) -> ASRResult:
        """Normalize audio, run VAD, and transcribe via configured ASR backend."""
        wav_path = audio_path.with_suffix(".16k.wav")
        if audio_path != wav_path:
            wav_path = normalize_to_wav16k(audio_path, wav_path)

        vad = analyze_wav_vad(wav_path)
        if vad.is_silent:
            return ASRResult(
                transcript="",
                detected_language=language_hint or "hi",
                confidence=0.12,
                duration_sec=vad.duration_sec,
                speech_ratio=vad.speech_ratio,
                provider="vad_gate",
            )

        provider = self.settings.asr_provider
        if provider == "mock" and transcript_hint:
            return ASRResult(
                transcript=transcript_hint.strip(),
                detected_language=language_hint or "hi",
                confidence=0.91,
                duration_sec=vad.duration_sec,
                speech_ratio=vad.speech_ratio,
                provider="mock",
            )

        # 1. Try Bhashini if configured
        if provider in ("auto", "bhashini") and self.settings.bhashini_api_key:
            try:
                return await self._transcribe_bhashini(wav_path, language_hint, vad)
            except Exception as exc:
                logger.warning("Bhashini ASR failed, falling back: %s", exc)

        # 2. Try local faster-whisper if installed
        if provider in ("auto", "whisper"):
            try:
                model = self._load_whisper()
                segments, info = model.transcribe(
                    str(wav_path),
                    language=language_hint if language_hint in ("hi", "mr", "en") else None,
                    vad_filter=True,
                )
                segs = list(segments)
                text = " ".join(s.text.strip() for s in segs).strip()
                avg_logprob = (
                    sum(s.avg_logprob for s in segs) / len(segs) if segs else -1.5
                )
                conf = max(0.05, min(0.99, float(1.0 + avg_logprob / 2.0)))
                # Penalize very low speech ratio
                if vad.speech_ratio < 0.2:
                    conf *= 0.7
                return ASRResult(
                    transcript=text,
                    detected_language=info.language or language_hint or "hi",
                    confidence=round(conf, 3),
                    duration_sec=vad.duration_sec,
                    speech_ratio=vad.speech_ratio,
                    provider="faster_whisper",
                )
            except ImportError:
                logger.info("faster-whisper not installed; using acoustic/hint fallback.")
            except Exception as exc:
                logger.warning("Whisper ASR error: %s", exc)

        # 3. Fallback when neither Bhashini nor Whisper is available locally
        if transcript_hint:
            conf = 0.88 if vad.speech_ratio >= 0.25 else 0.48
            return ASRResult(
                transcript=transcript_hint.strip(),
                detected_language=language_hint or "hi",
                confidence=conf,
                duration_sec=vad.duration_sec,
                speech_ratio=vad.speech_ratio,
                provider="acoustic_hint_fallback",
            )

        return ASRResult(
            transcript="",
            detected_language=language_hint or "hi",
            confidence=0.25,
            duration_sec=vad.duration_sec,
            speech_ratio=vad.speech_ratio,
            provider="unavailable_fallback",
        )

    async def _transcribe_bhashini(
        self, wav_path: Path, language_hint: str | None, vad
    ) -> ASRResult:
        audio_b64 = base64.b64encode(wav_path.read_bytes()).decode("ascii")
        lang = language_hint or "hi"
        payload = {
            "pipelineTasks": [
                {
                    "taskType": "asr",
                    "config": {
                        "language": {"sourceLanguage": lang},
                        "audioFormat": "wav",
                        "samplingRate": 16000,
                    },
                }
            ],
            "inputData": {"audio": [{"audioContent": audio_b64}]},
        }
        headers = {
            "userID": self.settings.bhashini_user_id,
            "ulcaApiKey": self.settings.bhashini_api_key,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://dhruva-api.bhashini.gov.in/services/inference/pipeline",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["pipelineResponse"][0]["output"][0]["source"].strip()
        return ASRResult(
            transcript=text,
            detected_language=lang,
            confidence=0.89 if text else 0.2,
            duration_sec=vad.duration_sec,
            speech_ratio=vad.speech_ratio,
            provider="bhashini",
        )
