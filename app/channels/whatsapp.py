"""WhatsApp Business Cloud API webhook handler, media download, and reply sender."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import get_settings
from app.db.database import Database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


def is_duplicate_message(db: Database, message_id: str) -> bool:
    with db.connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM processed_messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        if existing:
            return True
        conn.execute(
            "INSERT INTO processed_messages (message_id) VALUES (?)", (message_id,)
        )
    return False


async def download_whatsapp_media(media_id: str, access_token: str, dest: Path) -> Path:
    """Download OGG/Opus voice note from Meta Graph API."""
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        meta_resp = await client.get(
            f"https://graph.facebook.com/v20.0/{media_id}", headers=headers
        )
        meta_resp.raise_for_status()
        media_url = meta_resp.json()["url"]
        bin_resp = await client.get(media_url, headers=headers)
        bin_resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bin_resp.content)
    return dest


async def send_whatsapp_text(to_phone: str, text: str, access_token: str, phone_number_id: str) -> None:
    if not access_token or not phone_number_id:
        logger.info("WhatsApp credentials not set; skipping outbound text to %s", to_phone[-4:])
        return
    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    async with httpx.AsyncClient(timeout=15.0) as client:
        await client.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_phone,
                "type": "text",
                "text": {"body": text},
            },
        )


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    settings = get_settings()
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("")
async def receive_webhook(request: Request):
    payload = await request.json()
    pipeline = request.app.state.pipeline
    settings = get_settings()

    results = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                msg_id = msg.get("id", "")
                if msg_id and is_duplicate_message(pipeline.db, msg_id):
                    results.append({"message_id": msg_id, "status": "duplicate_ignored"})
                    continue

                from_phone = msg.get("from", "unknown")
                msg_type = msg.get("type")

                if msg_type == "text":
                    body = msg.get("text", {}).get("body", "")
                    resp = await pipeline.process_text(
                        text=body,
                        phone_number=from_phone,
                        channel="whatsapp",
                        synthesize_audio=True,
                    )
                    await send_whatsapp_text(
                        from_phone,
                        resp.answer_text,
                        settings.whatsapp_access_token,
                        settings.whatsapp_phone_number_id,
                    )
                    results.append({"message_id": msg_id, "interaction_id": resp.interaction_id, "decision": resp.decision})

                elif msg_type == "audio":
                    media_id = msg.get("audio", {}).get("id", "")
                    if settings.whatsapp_access_token and media_id:
                        dest = settings.audio_storage_dir / f"wa_{msg_id}.ogg"
                        await download_whatsapp_media(media_id, settings.whatsapp_access_token, dest)
                        resp = await pipeline.process_voice(
                            audio_path=dest,
                            phone_number=from_phone,
                            channel="whatsapp",
                        )
                    else:
                        # Local webhook simulation when Meta credentials are not configured
                        sim_text = msg.get("audio", {}).get("simulated_transcript", "")
                        resp = await pipeline.process_text(
                            text=sim_text or "",
                            phone_number=from_phone,
                            channel="whatsapp_voice_sim",
                            synthesize_audio=True,
                        )
                    results.append({"message_id": msg_id, "interaction_id": resp.interaction_id, "decision": resp.decision})

    return {"status": "ok", "processed": results}
