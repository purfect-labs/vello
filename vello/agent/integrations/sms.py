"""Twilio SMS adapter."""
from __future__ import annotations

import httpx

from vello.agent.tools import ToolUnavailable
from vello.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER

_BASE = "https://api.twilio.com/2010-04-01"
_COST_PER_SMS = 0.0079  # ~$0.0079 / message (Twilio US)


def _require_config() -> tuple[str, str, str]:
    missing = []
    if not TWILIO_ACCOUNT_SID:  missing.append("TWILIO_ACCOUNT_SID")
    if not TWILIO_AUTH_TOKEN:   missing.append("TWILIO_AUTH_TOKEN")
    if not TWILIO_FROM_NUMBER:  missing.append("TWILIO_FROM_NUMBER")
    if missing:
        raise ToolUnavailable(f"send_sms: {', '.join(missing)} not set")
    return TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER


def send_sms(to_number: str, body: str) -> dict:
    """
    Send an SMS via Twilio. `to_number` must be E.164 format.
    Returns {"sid": "...", "status": "queued"} on success.
    """
    account_sid, auth_token, from_number = _require_config()
    url = f"{_BASE}/Accounts/{account_sid}/Messages.json"
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                url,
                auth=(account_sid, auth_token),
                data={"To": to_number, "From": from_number, "Body": body[:1600]},
            )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        # Twilio returns JSON error bodies
        try:
            detail = exc.response.json().get("message", str(exc))
        except Exception:
            detail = str(exc)
        raise ToolUnavailable(f"send_sms: Twilio error — {detail}")
    except httpx.RequestError as exc:
        raise ToolUnavailable(f"send_sms: network error — {exc}")

    data = r.json()
    return {"sid": data.get("sid"), "status": data.get("status")}
