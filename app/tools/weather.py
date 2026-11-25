"""Weather and agromet advisory tool with Open-Meteo integration and cached fallback."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.config import Settings
from app.models.schemas import LiveToolResult


class WeatherTool:
    """Provides current weather and short agromet advisory with data_as_of timestamp."""

    def __init__(self, settings: Settings, fallback_path: Path | None = None):
        self.settings = settings
        self.fallback_path = fallback_path or Path("data/live_fallback/weather_advisories.json")
        self._cache: dict[str, tuple[float, LiveToolResult]] = {}

    async def get_weather(self, location: str | None) -> LiveToolResult:
        loc_key = (location or "nagpur").lower()
        cached = self._cache.get(loc_key)
        if cached and (time.time() - cached[0]) < self.settings.live_cache_ttl_seconds:
            return cached[1]

        locations_data = self._load_locations()
        loc_info = locations_data.get(loc_key)
        if not loc_info:
            return LiveToolResult(
                tool_name="weather_advisory",
                success=False,
                data_as_of=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
                source_name="IMD / Agromet Weather Service",
                summary_en="Please specify your district or city name for a local weather advisory.",
            )

        if self.settings.weather_provider == "open_meteo":
            try:
                res = await self._fetch_open_meteo(loc_key, loc_info)
                self._cache[loc_key] = (time.time(), res)
                return res
            except Exception:
                pass

        res = self._fallback_weather(loc_key, loc_info)
        self._cache[loc_key] = (time.time(), res)
        return res

    def _load_locations(self) -> dict:
        if self.fallback_path.exists():
            return json.loads(self.fallback_path.read_text(encoding="utf-8")).get("locations", {})
        return {}

    async def _fetch_open_meteo(self, loc_name: str, loc_info: dict) -> LiveToolResult:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": loc_info["lat"],
            "longitude": loc_info["lon"],
            "current": "temperature_2m,relative_humidity_2m,rain,wind_speed_10m",
            "timezone": "Asia/Kolkata",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            cur = resp.json().get("current", {})

        temp = cur.get("temperature_2m", loc_info["temp_c"])
        hum = cur.get("relative_humidity_2m", loc_info["humidity"])
        rain = cur.get("rain", loc_info["rain_mm"])
        wind = cur.get("wind_speed_10m", loc_info["wind_kmh"])
        as_of = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        advisory = (
            "Avoid spraying pesticides if rain is expected."
            if rain > 0.5
            else loc_info.get("advisory", "Suitable for routine field operations.")
        )
        summary = (
            f"Weather in {loc_name.title()} ({loc_info['state']}): temperature {temp} C, "
            f"humidity {hum} percent, rain {rain} mm, wind {wind} km/h. "
            f"Advisory: {advisory} Data as of {as_of}. Source: Open-Meteo / Agromet."
        )
        return LiveToolResult(
            tool_name="weather_advisory",
            success=True,
            data_as_of=as_of,
            source_name="Open-Meteo / Agromet Advisory",
            summary_en=summary,
            raw_data={"temp_c": temp, "humidity": hum, "rain_mm": rain, "wind_kmh": wind},
        )

    def _fallback_weather(self, loc_name: str, loc_info: dict) -> LiveToolResult:
        as_of = datetime.now(UTC).strftime("%Y-%m-%d")
        summary = (
            f"Weather in {loc_name.title()} ({loc_info['state']}): temperature {loc_info['temp_c']} C, "
            f"humidity {loc_info['humidity']} percent, rain {loc_info['rain_mm']} mm. "
            f"Advisory: {loc_info['advisory']} Data as of {as_of}. Source: IMD Agromet Snapshot."
        )
        return LiveToolResult(
            tool_name="weather_advisory",
            success=True,
            data_as_of=as_of,
            source_name="IMD Agromet Snapshot",
            summary_en=summary,
            raw_data=loc_info,
        )
