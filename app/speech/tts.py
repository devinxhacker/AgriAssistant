"""Text-to-Speech (TTS) service with Bhashini, edge-tts, macOS say, and WAV fallback."""

from __future__ import annotations

import logging
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from app.audio.processor import compress_to_ogg_opus
from app.config import Settings

logger = logging.getLogger(__name__)

EDGE_VOICES = {
    "hi": "hi-IN-SwaraNeural",
    "mr": "mr-IN-AarohiNeural",
    "en": "en-IN-NeerjaNeural",
}


class TTSService:
    """Synthesizes short, natural spoken replies and compresses them for low bandwidth."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def synthesize(
        self,
        text: str,
        language: str,
        output_stem: Path,
        compress_opus: bool = True,
    ) -> tuple[Path, float]:
        """Generate spoken audio file and return (file_path, duration_seconds)."""
        wav_path = output_stem.with_suffix(".wav")
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        provider = self.settings.tts_provider

        synthesized = False

        # 1. Try edge-tts if installed and requested/auto
        if not synthesized and provider in ("auto", "edge_tts"):
            try:
                import edge_tts  # type: ignore

                voice = EDGE_VOICES.get(language, EDGE_VOICES["hi"])
                mp3_path = output_stem.with_suffix(".mp3")
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(str(mp3_path))
                if mp3_path.exists() and mp3_path.stat().st_size > 0:
                    if compress_opus:
                        final_path = compress_to_ogg_opus(
                            mp3_path, output_stem.with_suffix(".ogg")
                        )
                        return final_path, self._estimate_duration(text)
                    return mp3_path, self._estimate_duration(text)
            except Exception as exc:
                logger.debug("edge-tts unavailable/failed: %s", exc)

        # 2. Try macOS `say` for local offline voice demo
        if not synthesized and provider in ("auto", "macos_say") and shutil.which("say"):
            aiff_path = output_stem.with_suffix(".aiff")
            voice_name = "Lekha" if language in ("hi", "mr") else "Samantha"
            proc = subprocess.run(
                ["say", "-v", voice_name, "-o", str(aiff_path), text],
                capture_output=True,
                timeout=20,
            )
            if proc.returncode == 0 and aiff_path.exists():
                ffmpeg = shutil.which("ffmpeg") or shutil.which("/opt/homebrew/bin/ffmpeg")
                if ffmpeg:
                    subprocess.run(
                        [ffmpeg, "-y", "-i", str(aiff_path), "-ar", "16000", "-ac", "1", str(wav_path)],
                        capture_output=True,
                        timeout=20,
                    )
                    aiff_path.unlink(missing_ok=True)
                    synthesized = wav_path.exists()

        # 3. Deterministic synthetic speech-cadence WAV fallback (always succeeds offline)
        if not synthesized:
            self._write_cadence_wav(wav_path, text)

        duration = self._wav_duration(wav_path)
        if compress_opus:
            final_path = compress_to_ogg_opus(wav_path, output_stem.with_suffix(".ogg"))
            return final_path, duration
        return wav_path, duration

    @staticmethod
    def _estimate_duration(text: str) -> float:
        words = max(1, len(text.split()))
        return round(min(30.0, max(1.5, words / 2.4)), 2)

    @staticmethod
    def _wav_duration(wav_path: Path) -> float:
        with wave.open(str(wav_path), "rb") as wf:
            return round(wf.getnframes() / float(wf.getframerate()), 2)

    @staticmethod
    def _write_cadence_wav(wav_path: Path, text: str, sample_rate: int = 16000) -> None:
        """Create a clean, low-amplitude spoken-cadence tone WAV when no neural TTS is available."""
        duration = min(4.0, max(1.0, len(text.split()) * 0.12))
        n_samples = int(sample_rate * duration)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            frames = bytearray()
            for i in range(n_samples):
                t = i / sample_rate
                envelope = 0.25 * (0.5 + 0.5 * math.sin(2 * math.pi * 3.5 * t))
                sample = int(32767 * envelope * math.sin(2 * math.pi * 240.0 * t))
                frames.extend(struct.pack("<h", sample))
            wf.writeframes(bytes(frames))
