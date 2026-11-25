"""Evaluation metrics: WER, chrF, Recall@k, Faithfulness, and Refusal Accuracy."""

from __future__ import annotations

import re
from collections import Counter


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Compute Levenshtein Word Error Rate (WER)."""
    ref_words = reference.strip().lower().split()
    hyp_words = hypothesis.strip().lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0

    dp = [[0] * (len(hyp_words) + 1) for _ in range(len(ref_words) + 1)]
    for i in range(len(ref_words) + 1):
        dp[i][0] = i
    for j in range(len(hyp_words) + 1):
        dp[0][j] = j

    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            cost = 0 if ref_words[i - 1] == hyp_words[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    return round(dp[len(ref_words)][len(hyp_words)] / len(ref_words), 4)


def chrf_score(reference: str, hypothesis: str, n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score (chrF) for translation quality evaluation."""
    ref = " ".join(reference.strip().split())
    hyp = " ".join(hypothesis.strip().split())
    if not ref or not hyp:
        return 0.0

    total_f = 0.0
    valid_n = 0
    for k in range(1, n + 1):
        ref_ngrams = Counter(ref[i : i + k] for i in range(max(0, len(ref) - k + 1)))
        hyp_ngrams = Counter(hyp[i : i + k] for i in range(max(0, len(hyp) - k + 1)))
        if not ref_ngrams or not hyp_ngrams:
            continue
        overlap = sum((ref_ngrams & hyp_ngrams).values())
        prec = overlap / sum(hyp_ngrams.values())
        rec = overlap / sum(ref_ngrams.values())
        if prec + rec > 0:
            f = (1 + beta**2) * prec * rec / ((beta**2) * prec + rec)
        else:
            f = 0.0
        total_f += f
        valid_n += 1
    return round((total_f / max(1, valid_n)) * 100.0, 2)


def faithfulness_score(answer_en: str, evidence_texts: list[str]) -> float:
    """Share of content tokens in the generated English answer supported by retrieved evidence."""
    stopwords = {
        "the", "is", "are", "in", "on", "of", "for", "to", "a", "an", "and", "or",
        "source", "data", "as", "with", "by", "from", "at", "be", "if", "your",
        "safety", "note", "always", "read", "product", "label", "wear", "gloves",
        "mask", "confirm", "dosage", "local", "kvk", "before", "spraying",
    }
    ans_tokens = [
        t for t in re.findall(r"[a-z0-9]+", answer_en.lower())
        if t not in stopwords and len(t) > 2
    ]
    if not ans_tokens:
        return 1.0
    ev_tokens = set(re.findall(r"[a-z0-9]+", " ".join(evidence_texts).lower()))
    supported = sum(1 for t in ans_tokens if t in ev_tokens)
    return round(supported / len(ans_tokens), 4)
