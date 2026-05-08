"""Resend transactional email adapter.

Thin wrapper over the resend SDK already used by vello/briefing.py.
"""
from __future__ import annotations

from vello.agent.tools import ToolUnavailable
from vello.config import RESEND_API_KEY, BRIEFING_FROM

_COST_PER_EMAIL = 0.0008


def _require_key() -> None:
    if not RESEND_API_KEY:
        raise ToolUnavailable("send_email: RESEND_API_KEY not set")


def send_email(to_address: str, subject: str, body_text: str,
               from_address: str | None = None) -> dict:
    """
    Send a plain-text email. For simple household notifications the text
    version is sufficient — no HTML rendering needed here.
    Returns {"id": "...", "sent": True} on success.
    """
    _require_key()
    from_addr = from_address or BRIEFING_FROM
    try:
        import resend
        resend.api_key = RESEND_API_KEY
        result = resend.Emails.send({
            "from":    from_addr,
            "to":      [to_address],
            "subject": subject,
            "text":    body_text,
        })
        return {"id": getattr(result, "id", str(result)), "sent": True}
    except Exception as exc:
        raise ToolUnavailable(f"send_email: Resend error — {exc}")
