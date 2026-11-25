# System Architecture — AgriAssistant

AgriAssistant is a voice-first, multilingual agricultural assistant built for Indian smallholder farmers, FPOs, and extension workers. It accepts spoken or text queries in **Marathi (`mr`)**, **Hindi (`hi`)**, **English (`en`)**, and code-mixed speech, retrieves grounded evidence from verified agricultural bulletins or live data tools, and replies with a short, cited voice note over WhatsApp or the web console.

## 1. Layered Architecture

```mermaid
flowchart TB
    User["Farmer (WhatsApp Voice Note / Web UI)"] --> Channel["1. Channel & Audio Layer\n(WhatsApp Cloud API, ffmpeg 16kHz WAV, Opus)"]
    Channel --> Speech["2. Speech Layer\n(VAD, Whisper / Bhashini ASR, Confidence)"]
    Speech --> NLU["3. Language & NLU Layer\n(LangID, Code-mix, Intent, Entities, Glossary Translation)"]
    NLU -->|Crop / Pest / Scheme| Retrieval["4. Hybrid Retrieval Layer\n(Dense + BM25 + RRF + Reranker + Metadata Filter)"]
    NLU -->|Mandi / Weather| Tools["5. Live Data Tools\n(Agmarknet / Open-Meteo + TTL Cache + data_as_of)"]
    Retrieval --> Gate["6. Confidence Gate & Guardrails\n(ASR, Rerank, Chemical Safety, KCC/KVK Referral)"]
    Tools --> Gate
    Gate -->|Answer| Gen["7. Grounded Generation & TTS\n(Extractive / LLM + Citation + Compressed OGG/Opus)"]
    Gate -->|Ask Repeat / Refuse| Gen
    Gen --> Channel
    Gen --> Platform["8. Platform & Evaluation Layer\n(SQLite/Postgres, Privacy Hashing, Admin Console, Eval Suite)"]
```

## 2. End-to-End Request Flow

```mermaid
sequenceDiagram
    participant F as Farmer (WhatsApp)
    participant W as Webhook & Audio
    participant A as ASR + VAD
    participant N as NLU & Glossary
    participant R as Hybrid RAG / Tools
    participant G as Confidence Gate
    participant T as Generator & TTS

    F->>W: Sends Marathi voice note (OGG/Opus)
    W->>W: Deduplicate message_id, normalize to 16kHz mono WAV
    W->>A: Run VAD & transcribe audio
    A-->>G: transcript + language + confidence
    alt Low ASR confidence or silent audio
        G-->>F: Polite "Ask to repeat" voice note
    else Clear speech
        A->>N: Detect language (hi/mr/en), intent, crop, region
        N->>R: Route to Hybrid RAG or Live Tool (mandi/weather)
        R-->>G: Top passages (approved only) or live data_as_of
        G->>T: Evaluate thresholds + chemical safety rule
        T-->>F: Short spoken reply (OGG/Opus < 30s) + source citation
    end
```

## 3. Module Inventory (14 Modules)

| # | Module | Implementation |
|---|---|---|
| 1 | Channel & Audio Interface | [whatsapp.py](file:///Users/kirannandi/Projects/AgriAssistant/app/channels/whatsapp.py), [processor.py](file:///Users/kirannandi/Projects/AgriAssistant/app/audio/processor.py) |
| 2 | Speech-to-Text (ASR) | [asr.py](file:///Users/kirannandi/Projects/AgriAssistant/app/speech/asr.py) |
| 3 | LangID, Intent & Entities | [query_understanding.py](file:///Users/kirannandi/Projects/AgriAssistant/app/nlp/query_understanding.py) |
| 4 | Glossary-Protected Translation | [translation.py](file:///Users/kirannandi/Projects/AgriAssistant/app/nlp/translation.py) |
| 5 | Knowledge Ingestion & Versioning | [cleaner.py](file:///Users/kirannandi/Projects/AgriAssistant/app/knowledge/cleaner.py), [ingestor.py](file:///Users/kirannandi/Projects/AgriAssistant/app/knowledge/ingestor.py) |
| 6 | Embeddings & Vector Store | [embeddings.py](file:///Users/kirannandi/Projects/AgriAssistant/app/retrieval/embeddings.py), [vector_store.py](file:///Users/kirannandi/Projects/AgriAssistant/app/retrieval/vector_store.py) |
| 7 | Hybrid Retrieval & Reranker | [bm25.py](file:///Users/kirannandi/Projects/AgriAssistant/app/retrieval/bm25.py), [hybrid.py](file:///Users/kirannandi/Projects/AgriAssistant/app/retrieval/hybrid.py) |
| 8 | Live Data Tools (Mandi & Weather) | [mandi.py](file:///Users/kirannandi/Projects/AgriAssistant/app/tools/mandi.py), [weather.py](file:///Users/kirannandi/Projects/AgriAssistant/app/tools/weather.py) |
| 9 | Grounded Answer Generation | [generator.py](file:///Users/kirannandi/Projects/AgriAssistant/app/generation/generator.py) |
| 10 | Confidence Gate & Fallback | [confidence_gate.py](file:///Users/kirannandi/Projects/AgriAssistant/app/safety/confidence_gate.py) |
| 11 | TTS & Low-Bandwidth Delivery | [tts.py](file:///Users/kirannandi/Projects/AgriAssistant/app/speech/tts.py) |
| 12 | Safety, Privacy & Compliance | [guardrails.py](file:///Users/kirannandi/Projects/AgriAssistant/app/safety/guardrails.py), [privacy.py](file:///Users/kirannandi/Projects/AgriAssistant/app/db/privacy.py) |
| 13 | Evaluation & Monitoring | [metrics.py](file:///Users/kirannandi/Projects/AgriAssistant/app/eval/metrics.py), [runner.py](file:///Users/kirannandi/Projects/AgriAssistant/app/eval/runner.py) |
| 14 | Admin Console & Expert Review | [admin.py](file:///Users/kirannandi/Projects/AgriAssistant/app/api/admin.py), `frontend/` |
