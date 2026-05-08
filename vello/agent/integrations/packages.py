"""
AfterShip package tracking adapter.

AfterShip's free tier supports ~100 tracking requests/month. When the key is
absent we fall back to a lightweight scrape of public carrier APIs where
possible. For MVP we keep it simple: require the key, raise ToolUnavailable
otherwise so the planner can route to a draft.
"""
from __future__ import annotations

import httpx

from vello.agent.tools import ToolUnavailable
from vello.config import AFTERSHIP_API_KEY

_BASE = "https://api.aftership.com/v4"
_COST_PER_CALL = 0.0


def _require_key() -> str:
    if not AFTERSHIP_API_KEY:
        raise ToolUnavailable("read_package_status: AFTERSHIP_API_KEY not set")
    return AFTERSHIP_API_KEY


def get_tracking(tracking_id: str, carrier: str | None = None) -> dict:
    """
    Fetch tracking status from AfterShip. `carrier` is the AfterShip slug
    (e.g. "ups", "fedex", "usps") — optional, AfterShip auto-detects.

    Returns a compact dict:
      {"tracking_id": ..., "status": "InTransit|Delivered|...",
       "last_update": iso, "location": "...", "eta": iso|None}
    """
    key = _require_key()
    # AfterShip uses an API key header, not Bearer
    headers = {"aftership-api-key": key, "Content-Type": "application/json"}

    # Try to detect existing tracking first
    url = f"{_BASE}/trackings/{tracking_id}"
    if carrier:
        url = f"{_BASE}/trackings/{carrier}/{tracking_id}"

    try:
        with httpx.Client(timeout=15) as client:
            r = client.get(url, headers=headers)
        if r.status_code == 404:
            # Not yet tracked — create it
            payload = {"tracking": {"tracking_number": tracking_id}}
            if carrier:
                payload["tracking"]["slug"] = carrier
            rc = client.post(f"{_BASE}/trackings", headers=headers, json=payload)
            rc.raise_for_status()
            r = rc
        else:
            r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolUnavailable(f"read_package_status: AfterShip returned {exc.response.status_code}")
    except httpx.RequestError as exc:
        raise ToolUnavailable(f"read_package_status: network error — {exc}")

    data = r.json().get("data", {}).get("tracking", {})
    checkpoints = data.get("checkpoints", [])
    last = checkpoints[-1] if checkpoints else {}

    return {
        "tracking_id":   tracking_id,
        "carrier":       data.get("slug", carrier or "unknown"),
        "status":        data.get("tag", "Unknown"),     # Delivered, InTransit, etc.
        "status_text":   data.get("subtag_message", ""),
        "last_update":   last.get("created_at"),
        "location":      last.get("location", ""),
        "eta":           data.get("expected_delivery"),
        "origin":        data.get("origin_country_iso3"),
        "destination":   data.get("destination_country_iso3"),
    }
