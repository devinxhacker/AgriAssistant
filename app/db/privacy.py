"""Privacy, consent, phone hashing, and audio retention enforcement."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.db.database import Database


def hash_phone(phone_number: str, salt: str = "agri_assistant_v1") -> str:
    """One-way SHA-256 hash so raw phone numbers are never stored in logs or DB."""
    normalized = "".join(ch for ch in phone_number if ch.isdigit())
    return hashlib.sha256(f"{salt}:{normalized}".encode()).hexdigest()[:24]


class PrivacyManager:
    def __init__(self, db: Database, audio_dir: Path, retention_hours: int = 72):
        self.db = db
        self.audio_dir = Path(audio_dir)
        self.retention_hours = retention_hours

    def get_or_create_session(self, raw_phone: str) -> dict:
        p_hash = hash_phone(raw_phone)
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE phone_hash = ?", (p_hash,)
            ).fetchone()
            if row:
                return dict(row)
            conn.execute(
                "INSERT INTO sessions (phone_hash, language_pref, consent_given) VALUES (?, 'hi', 0)",
                (p_hash,),
            )
            row = conn.execute(
                "SELECT * FROM sessions WHERE phone_hash = ?", (p_hash,)
            ).fetchone()
            return dict(row)

    def record_consent(self, raw_phone: str, granted: bool = True) -> None:
        p_hash = hash_phone(raw_phone)
        now = datetime.now(UTC).isoformat()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (phone_hash, consent_given, consent_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(phone_hash) DO UPDATE SET
                    consent_given = excluded.consent_given,
                    consent_at = excluded.consent_at,
                    updated_at = excluded.updated_at
                """,
                (p_hash, int(granted), now if granted else None, now),
            )

    def update_session_context(
        self,
        raw_phone: str,
        language_pref: str | None = None,
        last_region: str | None = None,
        last_crop: str | None = None,
    ) -> None:
        p_hash = hash_phone(raw_phone)
        self.get_or_create_session(raw_phone)
        with self.db.connection() as conn:
            if language_pref:
                conn.execute(
                    "UPDATE sessions SET language_pref = ?, updated_at = datetime('now') WHERE phone_hash = ?",
                    (language_pref, p_hash),
                )
            if last_region:
                conn.execute(
                    "UPDATE sessions SET last_region = ?, updated_at = datetime('now') WHERE phone_hash = ?",
                    (last_region, p_hash),
                )
            if last_crop:
                conn.execute(
                    "UPDATE sessions SET last_crop = ?, updated_at = datetime('now') WHERE phone_hash = ?",
                    (last_crop, p_hash),
                )

    def delete_user_data(self, phone_hash: str) -> dict[str, int]:
        """Right-to-erasure: delete session, anonymize interactions, and remove audio files."""
        removed_files = 0
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT audio_path FROM interactions WHERE phone_hash = ? AND audio_path IS NOT NULL",
                (phone_hash,),
            ).fetchall()
            for r in rows:
                path = Path(r["audio_path"])
                if path.exists():
                    path.unlink(missing_ok=True)
                    removed_files += 1
            cur_i = conn.execute(
                "DELETE FROM interactions WHERE phone_hash = ?", (phone_hash,)
            )
            cur_s = conn.execute(
                "DELETE FROM sessions WHERE phone_hash = ?", (phone_hash,)
            )
        return {
            "deleted_sessions": cur_s.rowcount,
            "deleted_interactions": cur_i.rowcount,
            "deleted_audio_files": removed_files,
        }

    def purge_expired_audio(self) -> int:
        """Delete voice recordings older than retention_hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=self.retention_hours)
        removed = 0
        if not self.audio_dir.exists():
            return 0
        for f in self.audio_dir.glob("*"):
            if f.is_file():
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    f.unlink(missing_ok=True)
                    removed += 1
        return removed
