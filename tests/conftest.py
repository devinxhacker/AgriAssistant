"""Shared pytest fixtures for isolated DB and pipeline testing."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db.database import Database
from app.main import create_app, seed_initial_data
from app.pipeline.orchestrator import AgriPipeline


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    return Settings(
        database_path=tmp_path / "test_agri.db",
        audio_storage_dir=tmp_path / "audio",
        asr_provider="mock",
        tts_provider="wav_tone",
        embedding_provider="char_ngram",
        llm_provider="extractive",
        weather_provider="fallback",
    )


@pytest.fixture
def seeded_pipeline(test_settings: Settings) -> AgriPipeline:
    db = Database(test_settings.database_path)
    pipeline = AgriPipeline(test_settings, db)
    seed_initial_data(db, pipeline)
    return pipeline


@pytest.fixture
def client(test_settings: Settings):
    app = create_app(test_settings)
    with TestClient(app) as c:
        yield c
