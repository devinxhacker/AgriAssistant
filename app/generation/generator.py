"""Grounded answer generation using LLM (when available) or extractive synthesis."""

from __future__ import annotations

import logging
import re

import httpx

from app.config import Settings
from app.models.schemas import RetrievedPassage
from app.retrieval.bm25 import tokenize

logger = logging.getLogger(__name__)


class GroundedAnswerGenerator:
    """Generates short, spoken-style, source-cited answers strictly from evidence."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def generate_from_passages(
        self,
        query_en: str,
        passages: list[RetrievedPassage],
    ) -> tuple[str, list[str]]:
        if not passages:
            return "", []

        sources = list(
            dict.fromkeys(
                p.metadata.get("source", "Verified Agricultural Advisory")
                for p in passages[:2]
            )
        )

        if self.settings.llm_provider in ("openai_compat", "ollama") or (
            self.settings.llm_provider == "auto" and self.settings.llm_api_key
        ):
            try:
                ans = await self._call_llm(query_en, passages[:3], sources)
                if ans:
                    return ans, sources
            except Exception as exc:
                logger.warning("LLM generation failed, using extractive fallback: %s", exc)

        return self._extractive_synthesize(query_en, passages[:2], sources), sources

    async def _call_llm(
        self, query_en: str, passages: list[RetrievedPassage], sources: list[str]
    ) -> str:
        evidence = "\n\n".join(
            f"[{i+1}] Source: {p.metadata.get('source', 'Advisory')}\n{p.text}"
            for i, p in enumerate(passages)
        )
        prompt = (
            "You are an agricultural advisor for Indian farmers. "
            "Answer the question using ONLY the evidence below. "
            "Keep the answer short (2 to 3 simple sentences suitable for voice playback under 30 seconds). "
            "Always state the source name. If the evidence does not cover something, say so.\n\n"
            f"Question: {query_en}\n\nEvidence:\n{evidence}\n\nAnswer:"
        )
        headers = {}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 180,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    @staticmethod
    def _extractive_synthesize(
        query_en: str, passages: list[RetrievedPassage], sources: list[str]
    ) -> str:
        """Deterministic extractive synthesis: selects top 2-3 relevant evidence sentences."""
        q_terms = set(tokenize(query_en))
        scored_sents: list[tuple[float, str]] = []

        for p in passages:
            lines = [ln.strip("-• ").strip() for ln in p.text.splitlines() if ln.strip()]
            for ln in lines:
                if ln.startswith("#") or ln.lower().startswith(("source:", "region:", "crop:", "season:", "publication date:")):
                    continue
                for sent in re.split(r"(?<=[.!?])\s+", ln):
                    sent = sent.strip()
                    if len(sent) < 20:
                        continue
                    s_terms = set(tokenize(sent))
                    overlap = len(q_terms & s_terms) / max(1, len(q_terms))
                    scored_sents.append((overlap + 0.25 * p.rerank_score, sent))

        scored_sents.sort(key=lambda x: x[0], reverse=True)
        chosen: list[str] = []
        seen = set()
        for _, sent in scored_sents:
            if sent not in seen:
                chosen.append(sent if sent.endswith(".") else f"{sent}.")
                seen.add(sent)
            if len(chosen) >= 3:
                break

        if not chosen:
            chosen = [passages[0].text[:240].strip()]

        cite_str = "; ".join(sources[:2])
        return f"{' '.join(chosen)} Source: {cite_str}."
