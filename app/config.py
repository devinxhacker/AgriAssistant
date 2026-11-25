"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_path: Path = Path("./storage/agri_assistant.db")
    audio_storage_dir: Path = Path("./storage/audio")
    audio_retention_hours: int = 72

    # Speech
    asr_provider: str = "auto"  # auto | whisper | bhashini | mock
    tts_provider: str = "auto"  # auto | edge_tts | bhashini | macos_say | wav_tone
    whisper_model_size: str = "small"
    bhashini_user_id: str = ""
    bhashini_api_key: str = ""
    bhashini_pipeline_id: str = ""

    # Translation & LLM
    translator_provider: str = "glossary_hybrid"
    llm_provider: str = "auto"  # auto | openai_compat | ollama | extractive
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen2.5:7b"

    # Retrieval
    embedding_provider: str = "auto"  # auto | sentence_transformers | char_ngram
    embedding_model: str = "BAAI/bge-m3"
    vector_store_backend: str = "sqlite"  # sqlite | qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "agri_kb"

    # Live tools
    mandi_api_key: str = ""
    weather_provider: str = "open_meteo"
    live_cache_ttl_seconds: int = 1800

    # WhatsApp
    whatsapp_verify_token: str = "sagveek_agri_verify_2026"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""

    # Safety & confidence thresholds
    asr_min_confidence: float = 0.55
    retrieval_min_score: float = 0.28
    faithfulness_min_score: float = 0.35
    kisan_call_centre: str = "1800-180-1551"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.audio_storage_dir.mkdir(parents=True, exist_ok=True)
    return settings
