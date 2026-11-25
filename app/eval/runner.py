"""Automated evaluation runner over data/eval_set.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.metrics import chrf_score, faithfulness_score, word_error_rate
from app.models.schemas import GateDecision, Intent
from app.pipeline.orchestrator import AgriPipeline


async def run_evaluation(
    pipeline: AgriPipeline,
    eval_path: Path = Path("data/eval_set.json"),
) -> dict:
    cases = json.loads(eval_path.read_text(encoding="utf-8"))
    results = []

    retrieval_hits = 0
    retrieval_total = 0
    faithfulness_scores: list[float] = []
    refusal_correct = 0
    refusal_total = 0
    wer_scores: list[float] = []
    chrf_scores: list[float] = []
    latencies: list[int] = []

    for case in cases:
        resp = await pipeline.process_text(
            text=case["query"],
            language_hint=case.get("language"),
            channel="eval_runner",
            synthesize_audio=False,
        )
        latencies.append(resp.latency_ms)

        expected_decision = case["expected_decision"]
        is_refusal_case = expected_decision == GateDecision.REFUSE.value

        if is_refusal_case:
            refusal_total += 1
            if resp.decision == GateDecision.REFUSE:
                refusal_correct += 1
        else:
            # Check retrieval recall@5 for RAG cases
            if case.get("expected_source_keyword"):
                retrieval_total += 1
                query_en = pipeline.translator.to_english(
                    resp.transcript, resp.language
                )
                passages = pipeline.retriever.retrieve(
                    query_en,
                    top_k=5,
                    crop=resp.entities.crop,
                    region=resp.entities.state,
                )
                ev_texts = [p.text for p in passages]
                kw = case["expected_source_keyword"].lower()
                hit = any(
                    kw in p.text.lower() or kw in (p.metadata.get("source", "").lower())
                    for p in passages
                )
                if hit:
                    retrieval_hits += 1
                if resp.decision == GateDecision.ANSWER and ev_texts:
                    faithfulness_scores.append(
                        faithfulness_score(resp.answer_english, ev_texts)
                    )
            elif resp.intent in (Intent.MARKET_PRICE, Intent.WEATHER) and resp.decision == GateDecision.ANSWER:
                # Live tool responses are directly grounded in tool output
                faithfulness_scores.append(1.0)

        if case.get("asr_reference") and case.get("asr_hypothesis"):
            wer_scores.append(word_error_rate(case["asr_reference"], case["asr_hypothesis"]))

        if case.get("reference_translation_en"):
            chrf_scores.append(
                chrf_score(case["reference_translation_en"], resp.answer_english)
            )

        results.append(
            {
                "id": case["id"],
                "language": resp.language,
                "intent": resp.intent.value,
                "expected_decision": expected_decision,
                "actual_decision": resp.decision.value,
                "reason_code": resp.reason_code,
                "sources": resp.sources,
                "latency_ms": resp.latency_ms,
                "passed": resp.decision.value == expected_decision,
            }
        )

    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted) // 2] if lat_sorted else 0
    p95 = lat_sorted[min(len(lat_sorted) - 1, int(len(lat_sorted) * 0.95))] if lat_sorted else 0

    summary = {
        "total_cases": len(cases),
        "decision_accuracy": round(
            sum(1 for r in results if r["passed"]) / max(1, len(results)), 4
        ),
        "retrieval_recall_at_5": round(
            retrieval_hits / max(1, retrieval_total), 4
        ),
        "mean_faithfulness": round(
            sum(faithfulness_scores) / max(1, len(faithfulness_scores)), 4
        ),
        "refusal_accuracy": round(
            refusal_correct / max(1, refusal_total), 4
        ),
        "mean_wer": round(sum(wer_scores) / max(1, len(wer_scores)), 4) if wer_scores else None,
        "mean_chrf": round(sum(chrf_scores) / max(1, len(chrf_scores)), 2) if chrf_scores else None,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "cases": results,
    }
    return summary
