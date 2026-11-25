# AgriAssistant — Voice-First Multilingual Agricultural Assistant

A voice-first, multilingual agricultural assistant for Indian farmers supporting **Marathi**, **Hindi**, **English**, and code-mixed speech over **WhatsApp Business Cloud API** and an interactive **Web Console**.

Every factual answer is grounded in verified agricultural bulletins (ICAR, state agricultural universities, MoA&FW scheme circulars) or timestamped live data tools (Agmarknet mandi prices and Open-Meteo/IMD agromet weather). When evidence or audio confidence is insufficient, the assistant safely declines and refers the farmer to the **Kisan Call Centre (1800-180-1551)** or local **KVK**.

## Key Features
- **Audio & Speech**: `ffmpeg` 16 kHz mono WAV normalization, energy-based VAD, Whisper / Bhashini ASR with per-utterance confidence, and compressed OGG/Opus TTS replies.
- **Multilingual NLU & Glossary**: Language ID (`mr`, `hi`, `en`), code-mixed handling, intent routing, entity extraction, and a protected agricultural glossary (`data/glossary.json`).
- **Verified Knowledge Base**: PyMuPDF + Tesseract OCR ingestion, structure-aware chunking, SHA-256 deduplication, versioning, and `approved`-only retrieval gating.
- **Hybrid Retrieval**: Dense embeddings + Okapi BM25 combined via Reciprocal Rank Fusion (RRF) and metadata-aware reranking.
- **Live Tools**: Mandi price and weather tools with TTL caching and mandatory `data_as_of` timestamps.
- **Safety & Privacy**: Content guardrails, chemical dosage safety notes, phone number SHA-256 hashing, audio retention purge, and right-to-erasure endpoint.
- **Admin Console & Evaluation**: React + Vite UI for Farmer Simulation, KB approval, glossary management, expert review queue, and automated evaluation (`Recall@5`, `Faithfulness`, `Refusal Accuracy`, `WER`, `chrF`).

## Quick Start

```bash
# 1. Setup Python environment
uv venv .venv --python python3.14
uv pip install -e ".[dev]"

# 2. Build Admin Console
cd frontend && npm install && npm run build && cd ..

# 3. Run automated tests (15/15 passing)
.venv/bin/pytest -v

# 4. Run evaluation benchmark
PYTHONPATH=. .venv/bin/python scripts/run_eval.py

# 5. Start server (http://localhost:8000)
./scripts/start_dev.sh
```

## Documentation
- [System Architecture](file:///Users/kirannandi/Projects/AgriAssistant/docs/architecture.md)
- [API Documentation](file:///Users/kirannandi/Projects/AgriAssistant/docs/api_documentation.md)
- [Deployment Guide](file:///Users/kirannandi/Projects/AgriAssistant/docs/deployment_guide.md)
- [Data Source Register](file:///Users/kirannandi/Projects/AgriAssistant/docs/data_source_register.md)
- [User Guide](file:///Users/kirannandi/Projects/AgriAssistant/docs/user_guide.md)
- [Evaluation Report](file:///Users/kirannandi/Projects/AgriAssistant/reports/evaluation_report.md)
