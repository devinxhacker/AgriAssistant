"""FastAPI application entrypoint and startup seeding."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.routes import router as api_router
from app.channels.whatsapp import router as whatsapp_router
from app.config import Settings, get_settings
from app.db.database import Database
from app.knowledge.ingestor import KnowledgeIngestor
from app.models.schemas import ApprovalStatus, DocumentMetadata
from app.pipeline.orchestrator import AgriPipeline


def seed_initial_data(db: Database, pipeline: AgriPipeline) -> None:
    """Seed glossary and verified knowledge base documents on initial startup."""
    glossary_path = Path("data/glossary.json")
    if glossary_path.exists():
        with db.connection() as conn:
            cnt = conn.execute("SELECT COUNT(*) FROM glossary_terms").fetchone()[0]
            if cnt == 0:
                terms = json.loads(glossary_path.read_text(encoding="utf-8"))
                for t in terms:
                    conn.execute(
                        "INSERT OR IGNORE INTO glossary_terms (term_id, category, en, hi, mr, notes) VALUES (?, ?, ?, ?, ?, ?)",
                        (t["term_id"], t["category"], t["en"], t["hi"], t["mr"], t.get("notes", "")),
                    )

    register_path = Path("data/data_source_register.json")
    if register_path.exists():
        with db.connection() as conn:
            doc_cnt = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if doc_cnt == 0:
            ingestor = KnowledgeIngestor(db, pipeline.embeddings)
            entries = json.loads(register_path.read_text(encoding="utf-8"))
            for item in entries:
                file_path = Path("data/kb_sources") / item["file"]
                if not file_path.exists():
                    continue
                meta = DocumentMetadata(
                    source=item["source"],
                    publisher=item["publisher"],
                    crop=item.get("crop"),
                    region=item.get("region"),
                    season=item.get("season"),
                    language=item.get("language", "en"),
                    publication_date=item["publication_date"],
                    version=item.get("version", "1.0"),
                    licence=item.get("licence", "Public Government Advisory"),
                    approval_status=ApprovalStatus(item.get("approval_status", "approved")),
                )
                ingestor.ingest_file(file_path, title=item["file"].replace(".md", "").replace("_", " ").title(), metadata=meta)


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = Database(settings.database_path)
        pipeline = AgriPipeline(settings, db)
        seed_initial_data(db, pipeline)
        app.state.settings = settings
        app.state.db = db
        app.state.pipeline = pipeline
        yield

    app = FastAPI(
        title="AgriAssistant — Voice-First Multilingual Agricultural Assistant",
        version="0.1.0",
        description="Sagveek Technologies Pvt. Ltd. — Grounded, voice-first agricultural assistant for Indian farmers.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(admin_router)
    app.include_router(whatsapp_router)

    frontend_dist = Path("frontend/dist")
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
