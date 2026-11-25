"""Pure-Python Okapi BM25 sparse retriever."""

from __future__ import annotations

import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\w\u0900-\u097F]+", text.lower())


class BM25Index:
    """In-memory Okapi BM25 scorer over approved chunks."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_ids: list[str] = []
        self.doc_freqs: list[Counter[str]] = []
        self.doc_lens: list[int] = []
        self.idf: dict[str, float] = {}
        self.avgdl: float = 1.0

    def build(self, items: list[tuple[str, str]]) -> None:
        """Build BM25 index from (chunk_id, text) pairs."""
        self.doc_ids = []
        self.doc_freqs = []
        self.doc_lens = []
        df: Counter[str] = Counter()

        for cid, text in items:
            tokens = tokenize(text)
            tf = Counter(tokens)
            self.doc_ids.append(cid)
            self.doc_freqs.append(tf)
            self.doc_lens.append(len(tokens))
            for term in tf:
                df[term] += 1

        n_docs = len(self.doc_ids)
        self.avgdl = sum(self.doc_lens) / max(1, n_docs)
        self.idf = {
            term: math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))
            for term, freq in df.items()
        }

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self.doc_ids:
            return []
        q_tokens = tokenize(query)
        scores: list[tuple[str, float]] = []
        for idx, cid in enumerate(self.doc_ids):
            tf = self.doc_freqs[idx]
            dl = self.doc_lens[idx]
            score = 0.0
            for term in q_tokens:
                if term not in tf:
                    continue
                f = tf[term]
                idf = self.idf.get(term, 0.0)
                denom = f + self.k1 * (1.0 - self.b + self.b * (dl / max(1.0, self.avgdl)))
                score += idf * (f * (self.k1 + 1.0)) / max(1e-8, denom)
            if score > 0.0:
                scores.append((cid, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
