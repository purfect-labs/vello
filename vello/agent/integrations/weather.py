"""OpenWeather current + forecast adapter."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from vello.agent.tools import ToolUnavailable
from vello.config import OPENWEATHER_API_KEY

_BASE = "https://api.openweathermap.org/data/2.5"
_COST_PER_CALL = 0.0  # free tier


def _require_key() -> str:
    if not OPENWEATHER_API_KEY:
        raise ToolUnavailable("read_weather: OPENWEATHER_API_KEY not set")
    return OPENWEATHER_API_KEY


def get_weather(lat: float, lng: float, days: int = 3) -> dict:
    """
    Returns a compact weather summary for lat/lng.
    Uses the free /forecast endpoint (3-hour steps, 5 days).
    """
    key = _require_key()
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{_BASE}/forecast",
                params={"lat": lat, "lon": lng, "appid": key, "units": "imperial", "cnt": min(days * 8, 40)},
            )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolUnavailable(f"read_weather: OpenWeather returned {exc.response.status_code}")
    except httpx.RequestError as exc:
        raise ToolUnavailable(f"read_weather: network error — {exc}")

    data = r.json()
    city = data.get("city", {}).get("name", "")
    entries = []
    for item in data.get("list", []):
        dt = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
        entries.append({
            "dt":          dt.strftime("%Y-%m-%d %H:%M"),
            "temp_f":      round(item["main"]["temp"]),
            "feels_f":     round(item["main"]["feels_like"]),
            "description": item["weather"][0]["description"] if item.get("weather") else "",
            "rain_mm":     item.get("rain", {}).get("3h", 0.0),
            "snow_mm":     item.get("snow", {}).get("3h", 0.0),
        })
    return {"city": city, "forecast": entries}


def get_current(lat: float, lng: float) -> dict:
    key = _require_key()
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{_BASE}/weather",
                params={"lat": lat, "lon": lng, "appid": key, "units": "imperial"},
            )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolUnavailable(f"read_weather: OpenWeather returned {exc.response.status_code}")
    except httpx.RequestError as exc:
        raise ToolUnavailable(f"read_weather: network error — {exc}")

    d = r.json()
    return {
        "temp_f":      round(d["main"]["temp"]),
        "feels_f":     round(d["main"]["feels_like"]),
        "description": d["weather"][0]["description"] if d.get("weather") else "",
        "humidity":    d["main"].get("humidity"),
        "wind_mph":    round(d.get("wind", {}).get("speed", 0)),
        "city":        d.get("name", ""),
    }
