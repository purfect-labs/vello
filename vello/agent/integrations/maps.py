"""Google Maps geocoding adapter."""
from __future__ import annotations

import httpx

from vello.agent.tools import ToolUnavailable
from vello.config import GMAPS_API_KEY

_BASE = "https://maps.googleapis.com/maps/api"
_COST_PER_CALL = 0.005  # ~$5 / 1000 calls


def _require_key() -> str:
    if not GMAPS_API_KEY:
        raise ToolUnavailable("geocode: GMAPS_API_KEY not set")
    return GMAPS_API_KEY


def geocode(address: str) -> dict:
    """Returns lat, lng, formatted_address or raises ToolUnavailable."""
    key = _require_key()
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{_BASE}/geocode/json",
                params={"address": address, "key": key},
            )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolUnavailable(f"geocode: Maps API returned {exc.response.status_code}")
    except httpx.RequestError as exc:
        raise ToolUnavailable(f"geocode: network error — {exc}")

    data = r.json()
    if data.get("status") == "REQUEST_DENIED":
        raise ToolUnavailable("geocode: Maps API key rejected (REQUEST_DENIED)")
    if data.get("status") != "OK" or not data.get("results"):
        raise ToolUnavailable(f"geocode: no results for address — {data.get('status')}")

    result = data["results"][0]
    loc = result["geometry"]["location"]
    return {
        "lat":               loc["lat"],
        "lng":               loc["lng"],
        "formatted_address": result.get("formatted_address", address),
    }


def reverse_geocode(lat: float, lng: float) -> dict:
    key = _require_key()
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                f"{_BASE}/geocode/json",
                params={"latlng": f"{lat},{lng}", "key": key},
            )
        r.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise ToolUnavailable(f"reverse_geocode: {exc}")

    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        return {"formatted_address": f"{lat},{lng}"}
    return {"formatted_address": data["results"][0].get("formatted_address", f"{lat},{lng}")}
