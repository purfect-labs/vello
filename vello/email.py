"""
Transactional email — verification + password reset.

Uses Resend (the same provider already wired for daily briefings). When
RESEND_API_KEY is unset the senders log a warning and return cleanly so dev
doesn't break — the user just won't receive an email. Verification + reset
flows still write tokens to the DB, so a developer with DB access can
complete the round-trip locally.
"""
from __future__ import annotations

import logging
from typing import Optional

import resend

from vello.config import APP_URL, BRIEFING_FROM, RESEND_API_KEY

log = logging.getLogger(__name__)


def _send(to: str, subject: str, html: str) -> Optional[dict]:
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping email to %s (%s)", to, subject)
        return None
    resend.api_key = RESEND_API_KEY
    try:
        return resend.Emails.send({
            "from":    BRIEFING_FROM,
            "to":      [to],
            "subject": subject,
            "html":    html,
        })
    except Exception as exc:
        log.error("Resend error for %s (%s): %s", to, subject, exc)
        return None


def send_verification_email(to: str, token: str) -> None:
    """Verify-email link is valid for 24 hours (enforced server-side by the DB layer)."""
    verify_url = f"{APP_URL}/verify-email?token={token}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Inter,system-ui,sans-serif;max-width:560px;margin:40px auto;color:#111">
  <h1 style="font-family:Georgia,serif;font-size:22px;font-weight:400">Verify your email for Vello</h1>
  <p>Click the link below to confirm this email address. The link expires in 24 hours.</p>
  <p><a href="{verify_url}" style="display:inline-block;padding:12px 22px;background:#f59e0b;color:#000;text-decoration:none;border-radius:6px;font-weight:600">Verify email</a></p>
  <p style="font-size:12px;color:#666">Or paste this URL into your browser:<br>{verify_url}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:11px;color:#999">If you didn't sign up for Vello, you can ignore this message.</p>
</body></html>"""
    _send(to, "Verify your Vello email", html)


def send_password_reset_email(to: str, token: str) -> None:
    """Reset link is valid for 1 hour."""
    reset_url = f"{APP_URL}/reset-password?token={token}"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:Inter,system-ui,sans-serif;max-width:560px;margin:40px auto;color:#111">
  <h1 style="font-family:Georgia,serif;font-size:22px;font-weight:400">Reset your Vello password</h1>
  <p>We received a request to reset your password. Click below to choose a new one. The link expires in 1 hour.</p>
  <p><a href="{reset_url}" style="display:inline-block;padding:12px 22px;background:#f59e0b;color:#000;text-decoration:none;border-radius:6px;font-weight:600">Reset password</a></p>
  <p style="font-size:12px;color:#666">Or paste this URL into your browser:<br>{reset_url}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:11px;color:#999">If you didn't request a reset, you can ignore this email — your password won't change.</p>
</body></html>"""
    _send(to, "Reset your Vello password", html)
