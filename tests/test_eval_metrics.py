"""Tests for automated evaluation metrics and benchmark runner."""

import pytest

from app.eval.metrics import chrf_score, faithfulness_score, word_error_rate
from app.eval.runner import run_evaluation


def test_metric_calculations():
    assert word_error_rate("cotton yellow leaves", "cotton yellow leaves") == 0.0
    assert word_error_rate("cotton yellow leaves", "cotton leaves") > 0.3
    assert chrf_score("Spray neem oil on cotton", "Spray neem oil on cotton") == 100.0
    assert faithfulness_score("Drain excess standing water from cotton field.", ["Drain excess standing water from the field immediately."]) > 0.7


@pytest.mark.asyncio
async def test_full_evaluation_meets_blueprint_targets(seeded_pipeline):
    summary = await run_evaluation(seeded_pipeline)
    assert summary["total_cases"] >= 15
    assert summary["retrieval_recall_at_5"] >= 0.85
    assert summary["mean_faithfulness"] >= 0.90
    assert summary["refusal_accuracy"] >= 0.90
    assert summary["decision_accuracy"] >= 0.90
