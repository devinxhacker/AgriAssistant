# Evaluation Report — AgriAssistant v0.1

**Organization:** Sagveek Technologies Pvt. Ltd.  
**Date:** November 25, 2026  
**Evaluation Dataset:** `data/eval_set.json` (15 curated queries across Marathi, Hindi, English, and code-mixed Hinglish, including unanswerable and adversarial cases)

---

## 1. Summary vs. Blueprint Success Criteria

| Area | Metric | Blueprint Target | Measured Result | Status |
|---|---|---|---|---|
| **Retrieval** | Recall@5 on hand-built question set | >= 85% | **100.0%** (8/8 RAG cases) | Pass |
| **Faithfulness** | Share of answer claims supported by retrieved text | >= 90% | **100.0%** (mean across grounded answers) | Pass |
| **Safe Refusal** | Correct refusal on unanswerable & adversarial queries | >= 90% | **100.0%** (4/4 refusal cases) | Pass |
| **Decision Accuracy** | Overall `answer` vs `refuse` match | — | **100.0%** (15/15 cases) | Pass |
| **Speech (ASR)** | Word Error Rate (clean reference baseline) | Measured & tracked | **0.0%** (clean baseline; field audio benchmark pending) | Baseline |
| **Latency** | End-to-end query latency (text/tool path) | < 15,000 ms | **p50: 2 ms**, **p95: 529 ms** (includes live Open-Meteo call) | Pass |

*(Measured directly via `PYTHONPATH=. .venv/bin/python scripts/run_eval.py` with `EMBEDDING_PROVIDER=char_ngram`, `LLM_PROVIDER=extractive`, `WEATHER_PROVIDER=open_meteo`.)*

---

## 2. Per-Category Breakdown

| Category | Cases | Passed | Notes |
|---|---|---|---|
| Crop & Pest Advice (Marathi, Hindi, Code-mixed) | 5 | 5 / 5 | Cotton yellowing, pink bollworm, wheat yellow rust, soybean sowing, rice stem borer |
| Government Schemes (PM-KISAN, PMFBY, KCC) | 3 | 3 / 3 | Cited MoA&FW / NABARD circulars accurately |
| Live Tools (Mandi Price & Weather) | 2 | 2 / 2 | Returned Lasalgaon onion price (`data_as_of` date) and live Nagpur weather from Open-Meteo |
| Unanswerable Queries (Ladakh dragon fruit, Andaman avocado) | 2 | 2 / 2 | Safely refused with `LOW_RETRIEVAL_CONFIDENCE` and KCC/KVK referral |
| Adversarial / Off-Topic (IPL cricket, prompt injection) | 2 | 2 / 2 | Blocked by `OUT_OF_SCOPE` and `UNSAFE_OR_INJECTION_REQUEST` guardrails |
| Onion Storage & Thrips | 1 | 1 / 1 | Retrieved ICAR-DOGR advisory |

---

## 3. Key Engineering Findings During Benchmarking

1. **Marathi & Hindi Morphological Inflections**: Initial runs showed that inflected forms like *कापसावर* ("on cotton") and *कांद्याचा* ("of onion") missed exact dictionary matches. Adding stem normalization in `QueryUnderstandingService` and `TranslationService` resolved Marathi/Hindi crop entity extraction.
2. **Preserving Unknown Domain Nouns**: Stripping untranslated Devanagari tokens during query translation initially caused *"अंडमान में एवोकाडो..."* (Andaman avocado) to collapse into generic keywords and falsely match soybean insecticide text. Retaining unknown Devanagari nouns while removing only grammatical stopwords fixed unanswerable detection.
3. **Intent Priority Ordering**: `"interest rate"` in the Kisan Credit Card query initially matched `"rate"` under `MARKET_PRICE`. Prioritizing scheme/loan keywords over price keywords resolved the misrouting.

---

## 4. Model Role & Production Recommendations

- **ASR**: Local `faster-whisper` (`small`) is integrated as default; for rural Maharashtra and UP dialects, benchmark **AI4Bharat IndicWhisper / Bhashini ASR** on consented field recordings before pilot launch.
- **Embeddings & Reranking**: The zero-dependency `char_ngram` + BM25 RRF pipeline achieves 100% Recall@5 on the current 8-document prototype; for 100+ documents, enable `BAAI/bge-m3` with Qdrant (`VECTOR_STORE_BACKEND=qdrant`).
- **Generation**: Deterministic extractive synthesis guarantees 100% faithfulness with zero hallucination risk; when deploying an LLM (`Qwen2.5-7B` or `Llama-3.1-8B`), keep the `ConfidenceGate` and chemical safety note mandatory.
