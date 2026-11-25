"""Tests for audio preprocessing, VAD, ASR confidence, and TTS."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from app.audio.processor import analyze_wav_vad, normalize_to_wav16k
from app.speech.tts import TTSService


def _make_wav(path: Path, freq: float = 300.0, amp: float = 0.3, duration: float = 1.2) -> Path:
    sr = 16000
    n = int(sr * duration)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        buf = bytearray()
        for i in range(n):
            val = int(32767 * amp * math.sin(2 * math.pi * freq * (i / sr)))
            buf.extend(struct.pack("<h", val))
        wf.writeframes(bytes(buf))
    return path


def test_vad_detects_silence_vs_speech(tmp_path):
    silent = _make_wav(tmp_path / "silent.wav", amp=0.0)
    speech = _make_wav(tmp_path / "speech.wav", amp=0.35)

    s_stats = analyze_wav_vad(silent)
    v_stats = analyze_wav_vad(speech)

    assert s_stats.is_silent is True
    assert v_stats.is_silent is False
    assert v_stats.speech_ratio > 0.8


def test_normalize_wav_and_tts(tmp_path, test_settings):
    src = _make_wav(tmp_path / "in.wav")
    out = normalize_to_wav16k(src, tmp_path / "out.16k.wav")
    assert out.exists()

    tts = TTSService(test_settings)
    import asyncio
    audio_file, dur = asyncio.run(
        tts.synthesize("Cotton advisory from ICAR.", "en", tmp_path / "tts_reply", compress_opus=False)
    )
    assert audio_file.exists()
    assert dur > 0.5


@pytest.mark.asyncio
async def test_silent_audio_triggers_ask_repeat(tmp_path, seeded_pipeline):
    silent = _make_wav(tmp_path / "silent_voice.wav", amp=0.0)
    resp = await seeded_pipeline.process_voice(silent, language_hint="mr")
    assert resp.decision.value == "ask_repeat"
    assert resp.reason_code == "LOW_ASR_CONFIDENCE"
    assert resp.audio_url is not None
