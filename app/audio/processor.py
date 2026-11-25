"""Audio preprocessing: ffmpeg transcoding, 16kHz mono WAV normalization, VAD, and Opus compression."""

from __future__ import annotations

import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class AudioStats:
    duration_sec: float
    sample_rate: int
    channels: int
    rms_db: float
    speech_ratio: float
    is_silent: bool


def find_ffmpeg() -> str | None:
    for candidate in ("ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def normalize_to_wav16k(input_path: Path, output_path: Path) -> Path:
    """Convert incoming voice note (OGG/Opus/MP3/WebM/WAV) to 16 kHz mono PCM WAV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-sample_fmt",
            "s16",
            str(output_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0 and output_path.exists():
            return output_path

    # Fallback: if already a WAV file, copy it
    if input_path.suffix.lower() == ".wav":
        shutil.copyfile(input_path, output_path)
        return output_path

    raise RuntimeError(
        f"Cannot normalize {input_path.name}: ffmpeg unavailable or conversion failed."
    )


def compress_to_ogg_opus(wav_path: Path, ogg_path: Path, bitrate: str = "24k") -> Path:
    """Compress WAV reply to low-bandwidth OGG/Opus for WhatsApp voice notes."""
    ogg_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(wav_path),
            "-c:a",
            "libopus",
            "-b:a",
            bitrate,
            "-vbr",
            "on",
            "-application",
            "voip",
            str(ogg_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0 and ogg_path.exists():
            return ogg_path
    # Fallback to WAV if opus encoder is absent
    return wav_path


def analyze_wav_vad(wav_path: Path, frame_ms: int = 30, energy_threshold: float = 0.012) -> AudioStats:
    """Compute duration, RMS level, and energy-based speech ratio from a PCM WAV file."""
    with wave.open(str(wav_path), "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if n_frames == 0:
        return AudioStats(0.0, sample_rate, channels, -90.0, 0.0, True)

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    duration_sec = len(samples) / float(sample_rate)
    rms = float(np.sqrt(np.mean(samples**2) + 1e-12))
    rms_db = float(20.0 * np.log10(max(rms, 1e-6)))

    frame_len = max(1, int(sample_rate * frame_ms / 1000))
    n_chunks = max(1, len(samples) // frame_len)
    trimmed = samples[: n_chunks * frame_len].reshape(n_chunks, frame_len)
    frame_rms = np.sqrt(np.mean(trimmed**2, axis=1))
    speech_frames = int(np.sum(frame_rms >= energy_threshold))
    speech_ratio = float(speech_frames / n_chunks)

    return AudioStats(
        duration_sec=round(duration_sec, 3),
        sample_rate=sample_rate,
        channels=channels,
        rms_db=round(rms_db, 2),
        speech_ratio=round(speech_ratio, 3),
        is_silent=(rms < 0.004 or speech_ratio < 0.05),
    )
