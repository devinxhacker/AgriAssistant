# API Documentation

Base URL: `http://localhost:8000` (Interactive OpenAPI docs available at `/docs`).

## 1. User & Voice Endpoints

### `GET /health`
Returns service health and count of approved knowledge base documents.

### `POST /api/v1/query`
Process a text query in Hindi, Marathi, English, or code-mixed text.
- **Request JSON**:
  ```json
  {
    "text": "माझ्या कापूस पिकाची पाने पिवळी पडत आहेत, काय करावे?",
    "language": "mr",
    "phone_number": "+919876543210",
    "synthesize_audio": true
  }
  ```
- **Response**: `AssistantResponse` containing `interaction_id`, `decision` (`answer` | `ask_repeat` | `refuse`), `reason_code`, `answer_text`, `answer_english`, `sources`, `data_as_of`, `audio_url`, `latency_ms`, and `confidence`.

### `POST /api/v1/voice`
Multipart upload for voice notes (`.ogg`, `.wav`, `.mp3`, `.webm`).
- **Form fields**: `audio` (file), `language` (optional), `transcript_hint` (optional for offline testing), `phone_number` (optional).

### `GET /api/v1/audio/{filename}`
Streams synthesized OGG/Opus or WAV reply audio.

### `POST /api/v1/feedback`
Record farmer/tester feedback (`1` = helpful, `-1` = needs expert review).

## 2. Privacy & Consent Endpoints

### `POST /api/v1/privacy/consent`
Record explicit user consent for voice processing (`{"phone_number": "...", "granted": true}`).

### `DELETE /api/v1/privacy/user/{phone_hash}`
Deletes user session, interaction logs, and stored audio files for the hashed phone identifier.

## 3. WhatsApp Cloud API Webhooks

- `GET /webhooks/whatsapp`: Meta webhook verification (`hub.mode`, `hub.verify_token`, `hub.challenge`).
- `POST /webhooks/whatsapp`: Receives WhatsApp text and audio messages with idempotent `message_id` deduplication.

## 4. Admin & Expert Review Endpoints

All `/api/v1/admin/*` routes enforce role-based access via `X-Admin-Role` (`admin`, `reviewer`, `analyst`).

- `GET /api/v1/admin/documents` — List all KB documents and chunk counts.
- `POST /api/v1/admin/documents/ingest-text` — Ingest structured text with metadata (`admin`, `reviewer`).
- `POST /api/v1/admin/documents/upload` — Upload `.pdf`, `.md`, `.txt`, or `.html` (`admin`, `reviewer`).
- `POST /api/v1/admin/documents/{doc_id}/approval?status=approved|rejected` — Approve or reject a document (`admin`, `reviewer`).
- `GET /api/v1/admin/glossary` / `POST /api/v1/admin/glossary` — View or add multilingual glossary terms.
- `GET /api/v1/admin/review-queue` — List low-confidence, refused, or negatively rated interactions.
- `POST /api/v1/admin/review-queue/correct` — Save expert correction and optionally promote to `data/eval_set.json`.
- `POST /api/v1/admin/eval/run` — Execute automated evaluation benchmark.
- `GET /metrics` — Prometheus metrics (`agri_queries_total`, `agri_query_latency_seconds`).
