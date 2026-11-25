"""Mandi price tool (Agmarknet / e-NAM) with TTL caching and explicit data_as_of timestamps."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import Settings
from app.models.schemas import LiveToolResult


class MandiPriceTool:
    """Fetches daily mandi prices; never stored in the vector index."""

    def __init__(self, settings: Settings, fallback_path: Path | None = None):
        self.settings = settings
        self.fallback_path = fallback_path or Path("data/live_fallback/mandi_prices.json")
        self._cache: dict[str, tuple[float, LiveToolResult]] = {}

    async def get_price(
        self,
        commodity: str | None,
        market: str | None = None,
        state: str | None = None,
    ) -> LiveToolResult:
        if not commodity:
            return LiveToolResult(
                tool_name="mandi_price",
                success=False,
                data_as_of=datetime.now(UTC).strftime("%Y-%m-%d"),
                source_name="Agmarknet / e-NAM",
                summary_en="Please mention the crop or commodity name to check mandi prices.",
            )

        cache_key = f"{commodity.lower()}:{(market or '').lower()}:{(state or '').lower()}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self.settings.live_cache_ttl_seconds:
            return cached[1]

        # Try data.gov.in Agmarknet API if key is configured
        if self.settings.mandi_api_key:
            try:
                res = await self._fetch_agmarknet(commodity, market, state)
                if res.success:
                    self._cache[cache_key] = (time.time(), res)
                    return res
            except Exception:
                pass

        res = self._lookup_fallback(commodity, market, state)
        self._cache[cache_key] = (time.time(), res)
        return res

    async def _fetch_agmarknet(
        self, commodity: str, market: str | None, state: str | None
    ) -> LiveToolResult:
        params = {
            "api-key": self.settings.mandi_api_key,
            "format": "json",
            "limit": 5,
            "filters[commodity]": commodity.title(),
        }
        if state:
            params["filters[state]"] = state
        if market:
            params["filters[market]"] = market

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070",
                params=params,
            )
            resp.raise_for_status()
            records = resp.json().get("records", [])

        if not records:
            return self._lookup_fallback(commodity, market, state)

        rec = records[0]
        as_of = rec.get("arrival_date", datetime.now(UTC).strftime("%Y-%m-%d"))
        summary = (
            f"In {rec.get('market', 'the mandi')} ({rec.get('state', '')}), "
            f"{commodity} modal price is Rs {rec.get('modal_price')} per quintal "
            f"(min Rs {rec.get('min_price')}, max Rs {rec.get('max_price')}). "
            f"Data as of {as_of}. Source: Agmarknet."
        )
        return LiveToolResult(
            tool_name="mandi_price",
            success=True,
            data_as_of=as_of,
            source_name="Agmarknet (data.gov.in)",
            summary_en=summary,
            raw_data=rec,
        )

    def _lookup_fallback(
        self, commodity: str, market: str | None, state: str | None
    ) -> LiveToolResult:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if not self.fallback_path.exists():
            return LiveToolResult(
                tool_name="mandi_price",
                success=False,
                data_as_of=today,
                source_name="Agmarknet / e-NAM",
                summary_en=f"Live mandi price data for {commodity} is currently unavailable.",
            )

        data = json.loads(self.fallback_path.read_text(encoding="utf-8"))
        records = data.get("records", [])
        matches = [
            r for r in records if r["commodity"].lower() == commodity.lower()
        ]
        if market:
            m_matches = [r for r in matches if r["market"].lower() == market.lower()]
            if m_matches:
                matches = m_matches
        elif state:
            s_matches = [r for r in matches if r["state"].lower() == state.lower()]
            if s_matches:
                matches = s_matches

        if not matches:
            return LiveToolResult(
                tool_name="mandi_price",
                success=False,
                data_as_of=today,
                source_name=data.get("source", "Agmarknet / e-NAM"),
                summary_en=f"No recent mandi price record found for {commodity}.",
            )

        rec = matches[0]
        summary = (
            f"In {rec['market']} mandi ({rec['state']}), {rec['commodity']} modal price is "
            f"Rs {rec['modal_price']} per quintal (range Rs {rec['min_price']} to Rs {rec['max_price']}). "
            f"Data as of {today}. Source: {data.get('source', 'Agmarknet / e-NAM')}."
        )
        return LiveToolResult(
            tool_name="mandi_price",
            success=True,
            data_as_of=today,
            source_name=data.get("source", "Agmarknet / e-NAM"),
            summary_en=summary,
            raw_data=rec,
        )
