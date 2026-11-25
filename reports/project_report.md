# Project Report: Voice-First Multilingual Agricultural Assistant (AgriAssistant)

---

**Submitted By:** Kiran Nandi  
**PRN:** 202301040001  
**Subject:** Generative AI (MDM)  
**Assessment:** Internal Assessment 2 (IA 2)  
**Date:** November 25, 2026  

---

## 1. Abstract & Problem Statement

Timely agricultural decisions—such as diagnosing crop yellowing, selecting safe pesticide dosages, checking daily mandi rates, or applying for government schemes—are often hindered because official advisories are published as dense PDFs in English or formal Hindi, while market prices and weather alerts live on separate portals. Many smallholder farmers prefer speaking in regional languages (such as Marathi and Hindi) over typing, and operate on basic smartphones with intermittent internet access.

**Problem Statement:**  
Design and develop a voice-first, multilingual assistant for Indian farmers that accepts spoken questions in selected Indic languages (`mr`, `hi`, `en`), retrieves answers from verified agricultural knowledge sources and live data services, generates a short, simple, source-cited response in the farmer's language, and speaks it back over low-bandwidth channels (such as WhatsApp voice notes), while declining safely when evidence or confidence is insufficient.

---

## 2. Objectives

1. **Multilingual Voice Support**: Support spoken and text input/output in Marathi (`mr`), Hindi (`hi`), English (`en`), and code-mixed speech.
2. **Domain Coverage**: Answer crop-advice, pest/disease, government-scheme (PM-KISAN, PMFBY, KCC), live mandi-price, and weather/agromet questions.
3. **Strict Grounding & Citations**: Ground every factual answer in an approved, retrievable source and cite the source name (plus `data_as_of` dates for live tools).
4. **Low-Bandwidth Readiness**: Keep replies concise (target under 30 seconds spoken) and compress audio to OGG/Opus.
5. **Safe Refusal & Chemical Guardrails**: Detect low ASR/retrieval confidence or out-of-scope queries and refuse safely with referral to the **Kisan Call Centre (`1800-180-1551`)** or local **Krishi Vigyan Kendra (KVK)**, and append mandatory safety notes for chemical/pesticide advice.
6. **Measurable Evaluation**: Track Retrieval Recall@5, Faithfulness, Safe Refusal Accuracy, Word Error Rate (WER), and end-to-end latency.

---

## 3. System Architecture

The platform is organized into eight cohesive layers implemented across 14 backend modules and a React + Vite Admin & Farmer Simulator Console.

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

### End-to-End Request Flow

```mermaid
sequenceDiagram
    participant F as Farmer (WhatsApp / Web)
    participant W as Channel & Audio
    participant A as ASR + VAD
    participant N as NLU & Glossary
    participant R as Hybrid RAG / Live Tools
    participant G as Confidence Gate
    participant T as Generator & TTS

    F->>W: Sends Marathi voice note (OGG/Opus)
    W->>W: Deduplicate message_id, normalize to 16kHz mono WAV
    W->>A: Run VAD & transcribe audio
    A-->>G: Transcript + language + confidence
    alt Low ASR confidence or silent audio
        G-->>F: Polite "Ask to repeat" voice note
    else Clear speech
        A->>N: Detect language (mr/hi/en), intent, crop, region
        N->>R: Route to Hybrid RAG or Live Tool (mandi/weather)
        R-->>G: Top passages (approved only) or live data_as_of
        G->>T: Evaluate thresholds + chemical safety rule
        T-->>F: Short spoken reply (OGG/Opus) + source citation
    end
```

---

## 4. Key Implementation Details

| Component | Technology & Design Choice |
|---|---|
| **Backend API** | Python 3.14, FastAPI, Pydantic v2, Uvicorn |
| **Audio & Speech** | `ffmpeg` (16 kHz mono WAV & OGG/Opus compression), energy-based VAD, Whisper / Bhashini ASR, `edge-tts` / macOS `say` / WAV TTS |
| **NLU & Glossary** | Morphological stem-aware Marathi/Hindi/code-mixed LangID, intent routing, and a 22-term protected EN/HI/MR agricultural glossary |
| **Knowledge Ingestion** | PyMuPDF + Tesseract OCR fallback, structure-aware markdown chunking, SHA-256 deduplication, and `approved`-only retrieval |
| **Hybrid Retrieval** | Dense embeddings + Okapi BM25 combined via Reciprocal Rank Fusion (RRF) and metadata-aware reranking |
| **Live Data Tools** | Agmarknet mandi prices and Open-Meteo / IMD agromet weather with 30-minute TTL cache (never indexed in vector store) |
| **Safety & Privacy** | Prompt-injection/off-topic guardrails, SHA-256 phone number hashing, consent tracking, and right-to-erasure endpoint |
| **Admin Console** | React 19 + Vite single-page application served directly by FastAPI |

---

## 5. Application Screenshots & Walkthrough

### 5.1 Farmer Simulator (Marathi Query with Audio Reply & Safety Note)
The Farmer Simulator demonstrates an end-to-end Marathi query (*"माझ्या कापूस पिकाची पाने पिवळी पडत आहेत, काय करावे?"*). The system detects `mr` (`pest_disease` intent), retrieves the approved **ICAR-Central Institute for Cotton Research (CICR), Nagpur** advisory, returns a grounded response with `92%` confidence in `1003 ms`, appends the mandatory Marathi chemical safety note, and synthesizes a 4-second playable voice reply.

![Farmer Simulator showing Marathi cotton yellowing query and grounded audio response](./screenshots/01_farmer_simulator.jpg)

### 5.2 Verified Knowledge Base Management
The Knowledge Base tab displays all 8 ingested agricultural bulletins and government scheme circulars (PMFBY, KCC, PM-KISAN, ICAR Wheat, ICAR Soybean, DOGR Onion, ICAR Rice, ICAR Cotton) with crop/region tags, source publisher, version, chunk count, and role-based **Approve / Reject** controls.

![Verified Knowledge Base tab showing 8 approved documents and chunk counts](./screenshots/02_knowledge_base.png)

### 5.3 Multilingual Agricultural Glossary
The Glossary tab manages 22 domain-specific terms across English, Hindi, and Marathi (chemicals such as *Imidacloprid 17.8 SL*, *Neem oil 1500 ppm*, *DAP*, *urea*; crops; pests; and market terms) so critical agricultural terminology is never mistranslated.

![Multilingual Agricultural Glossary tab showing 22 EN/HI/MR terms](./screenshots/03_glossary.png)

### 5.4 Automated Evaluation Suite & Expert Review Queue
The Eval & Review tab executes the automated benchmark over `data/eval_set.json` and surfaces low-confidence, refused, or negatively rated queries in the Expert Review Queue for human-in-the-loop correction.

![Automated Evaluation Suite and Expert Review Queue showing 100% Recall@5, Faithfulness, and Safe Refusal](./screenshots/04_eval_and_review.jpg)

---

## 6. Evaluation & Testing Results

### 6.1 Automated Benchmark (`data/eval_set.json` — 15 Queries)

| Metric | Blueprint Target | Measured Result | Status |
|---|---|---|---|
| **Retrieval Recall@5** | >= 85% | **100.0%** | Pass |
| **Faithfulness** | >= 90% | **100.0%** | Pass |
| **Safe Refusal Accuracy** | >= 90% | **100.0%** | Pass |
| **Decision Accuracy** | — | **100.0%** (15/15) | Pass |
| **p95 Latency** | < 15,000 ms | **678 ms** (UI run) / **529 ms** (CLI run) | Pass |

### 6.2 Unit & Integration Test Suite (`pytest`)
All **15/15** automated tests pass in `0.36s`, covering:
- Audio VAD silence detection, WAV normalization, and TTS generation (`test_audio_and_asr.py`)
- Marathi/Hindi/code-mixed detection and glossary-protected translation (`test_nlp_and_glossary.py`)
- Document deduplication, `pending` vs `approved` retrieval gating, and hybrid RRF retrieval (`test_knowledge_and_retrieval.py`)
- Live mandi/weather `data_as_of` timestamps, chemical safety notes, and prompt-injection/off-topic refusal (`test_tools_and_safety.py`)
- FastAPI endpoints, WhatsApp webhook verification & deduplication, RBAC, and privacy erasure (`test_pipeline_and_api.py`)
- Automated evaluation metrics (`test_eval_metrics.py`)

---

## 7. Conclusion & Future Scope

AgriAssistant demonstrates that a voice-first, retrieval-grounded architecture can deliver trustworthy, low-latency agricultural guidance in regional Indian languages while strictly avoiding hallucinations on out-of-scope or unverified queries.

**Future Scope:**
- Photo-based crop disease diagnosis using a vision-language model
- Fine-tuned Indic ASR on consented rural dialect field recordings
- IVR / missed-call support for feature-phone users
- Proactive weather and sowing-window alerts via WhatsApp templates
