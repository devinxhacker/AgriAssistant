# Deployment Guide

## 1. Local Development Setup

### Prerequisites
- Python 3.11+ (`uv` or `pip`)
- Node.js 20+ (for building the Admin Console)
- `ffmpeg` (for OGG/Opus <-> 16 kHz mono WAV transcoding)
- Optional: `tesseract` (for OCR on scanned PDFs)

### Steps
```bash
# 1. Create virtual environment and install backend
uv venv .venv --python python3.14
uv pip install -e ".[dev]"

# 2. Copy environment config
cp .env.example .env

# 3. Build the React Admin Console
cd frontend && npm install && npm run build && cd ..

# 4. Seed the knowledge base & run tests
PYTHONPATH=. .venv/bin/python scripts/seed_kb.py
.venv/bin/pytest -v

# 5. Start the API + Web Console
./scripts/start_dev.sh
```
Open `http://localhost:8000` for the Farmer Simulator & Admin Console, or `http://localhost:8000/docs` for Swagger API docs.

## 2. Production / Optional ML Backends

To enable full neural ASR, embeddings, and neural TTS in production:
```bash
uv pip install -e ".[ml]"
```
Then configure `.env`:
- **ASR**: Set `ASR_PROVIDER=whisper` (`WHISPER_MODEL_SIZE=small`) or `ASR_PROVIDER=bhashini` with `BHASHINI_USER_ID` and `BHASHINI_API_KEY`.
- **LLM**: Set `LLM_PROVIDER=ollama` (with local `qwen2.5:7b` or `llama3.1:8b`) or `LLM_PROVIDER=openai_compat`.
- **Vector Store**: Set `VECTOR_STORE_BACKEND=qdrant` and `QDRANT_URL=http://qdrant:6333`.
- **WhatsApp**: Configure `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, and `WHATSAPP_PHONE_NUMBER_ID` in Meta Developer Console.

## 3. Docker Compose Deployment

```bash
docker compose up --build -d
```
This starts the FastAPI backend (`:8000`), Redis (`:6379`), and Qdrant (`:6333`) with persistent volumes for `./storage` and `./data`.
