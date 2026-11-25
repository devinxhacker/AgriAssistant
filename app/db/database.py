"""SQLite database management for documents, chunks, sessions, interactions, and glossary."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source TEXT NOT NULL,
    publisher TEXT NOT NULL,
    crop TEXT,
    region TEXT,
    season TEXT,
    language TEXT NOT NULL DEFAULT 'en',
    publication_date TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0',
    licence TEXT NOT NULL DEFAULT 'Public / Government Advisory',
    approval_status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(approval_status);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);

CREATE TABLE IF NOT EXISTS sessions (
    phone_hash TEXT PRIMARY KEY,
    language_pref TEXT NOT NULL DEFAULT 'hi',
    last_region TEXT,
    last_crop TEXT,
    consent_given INTEGER NOT NULL DEFAULT 0,
    consent_at TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interactions (
    interaction_id TEXT PRIMARY KEY,
    phone_hash TEXT,
    channel TEXT NOT NULL DEFAULT 'api',
    language TEXT NOT NULL,
    transcript TEXT NOT NULL,
    intent TEXT NOT NULL,
    entities_json TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    answer_english TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    audio_path TEXT,
    feedback_rating INTEGER,
    feedback_comment TEXT,
    reviewed_by TEXT,
    corrected_answer TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_interactions_decision ON interactions(decision);
CREATE INDEX IF NOT EXISTS idx_interactions_created ON interactions(created_at);

CREATE TABLE IF NOT EXISTS processed_messages (
    message_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS glossary_terms (
    term_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    en TEXT NOT NULL,
    hi TEXT NOT NULL,
    mr TEXT NOT NULL,
    notes TEXT DEFAULT ''
);
"""


class Database:
    """Thread-safe lightweight SQLite wrapper."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
