"""
Daily briefing — generate HTML email and send via Resend.
"""
import json
import logging
from datetime import datetime, timezone

import resend

from vello.config import RESEND_API_KEY, BRIEFING_FROM, APP_URL
from vello.database import (
    get_connection, get_context, get_active_triggers,
    get_temporal_patterns, get_pending_inferences,
)
from vello.gaps import detect_gaps

log = logging.getLogger(__name__)


def _get_briefing_data(user_id: str) -> dict:
    context_rows  = get_context(user_id)
    triggers      = get_active_triggers(user_id)[:5]
    patterns      = get_temporal_patterns(user_id)
    gaps          = detect_gaps(user_id)[:3]
    inferences    = get_pending_inferences(user_id)[:3]

    name = "there"
    for r in context_rows:
        if r["domain"] == "identity" and r["key"] in ("name", "first_name"):
            name = r["value"].split()[0]
            break

    return {
        "name":       name,
        "triggers":   [dict(t) for t in triggers],
        "patterns":   [dict(p) for p in patterns],
        "gaps":       [dict(g) for g in gaps],
        "inferences": [dict(i) for i in inferences],
    }


def _render_html(data: dict, date_str: str) -> str:
    name      = data["name"]
    triggers  = data["triggers"]
    patterns  = data["patterns"]
    gaps      = data["gaps"]
    inferences = data["inferences"]

    def signal_block() -> str:
        if not triggers:
            return ""
        items = "".join(
            f'<tr><td style="padding:8px 0;border-bottom:1px solid #1a1814">'
            f'<span style="color:#f59e0b;font-size:11px;font-family:monospace;text-transform:uppercase">'
            f'{t["priority"]}</span><br>'
            f'<span style="color:#f6f3ee;font-size:14px">{t["trigger_message"]}</span>'
            f'</td></tr>'
            for t in triggers
        )
        return f"""
        <h2 style="font-family:Georgia,serif;color:#f6f3ee;font-size:18px;margin:32px 0 12px">Signals</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1a1814">
          {items}
        </table>"""

    def pattern_block() -> str:
        if not patterns:
            return ""
        items = "".join(
            f'<tr><td style="padding:8px 0;border-bottom:1px solid #1a1814">'
            f'<span style="color:#8c8680;font-size:12px;font-family:monospace">{p["label"]}</span><br>'
            f'<span style="color:#f6f3ee;font-size:13px">'
            f'Typical: {int(p["mean_minutes"] or 0) // 60:02d}:{int(p["mean_minutes"] or 0) % 60:02d}'
            f'</span></td></tr>'
            for p in patterns if p.get("sample_count", 0) >= 3
        )
        if not items:
            return ""
        return f"""
        <h2 style="font-family:Georgia,serif;color:#f6f3ee;font-size:18px;margin:32px 0 12px">Patterns</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1a1814">
          {items}
        </table>"""

    def gap_block() -> str:
        if not gaps:
            return ""
        items = "".join(
            f'<tr><td style="padding:8px 0;border-bottom:1px solid #1a1814">'
            f'<span style="color:#f59e0b;font-size:12px;font-family:monospace">{g["domain"].upper()} · {g["key"]}</span><br>'
            f'<span style="color:#8c8680;font-size:13px">{g.get("reason","")}</span>'
            f'</td></tr>'
            for g in gaps
        )
        return f"""
        <h2 style="font-family:Georgia,serif;color:#f6f3ee;font-size:18px;margin:32px 0 12px">Gaps</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1a1814">
          {items}
        </table>"""

    def inference_block() -> str:
        if not inferences:
            return ""
        items = "".join(
            f'<tr><td style="padding:8px 0;border-bottom:1px solid #1a1814">'
            f'<span style="color:#8c8680;font-size:13px;font-style:italic">{i["description"]}</span>'
            f'</td></tr>'
            for i in inferences
        )
        return f"""
        <h2 style="font-family:Georgia,serif;color:#f6f3ee;font-size:18px;margin:32px 0 12px">Observations</h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #1a1814">
          {items}
        </table>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#000000;font-family:Inter,-apple-system,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#000000;padding:40px 0">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%">
        <tr><td style="padding:0 24px">

          <!-- Header -->
          <p style="margin:0 0 4px;font-family:monospace;font-size:11px;color:#3a3733;text-transform:uppercase;letter-spacing:.08em">
            {date_str}
          </p>
          <h1 style="margin:0 0 8px;font-family:Georgia,serif;font-size:28px;color:#f6f3ee;font-weight:400">
            Good morning, {name}.
          </h1>
          <p style="margin:0 0 32px;color:#8c8680;font-size:14px">
            Here's your Vello briefing.
          </p>

          <!-- Divider -->
          <hr style="border:none;border-top:1px solid #1a1814;margin:0 0 24px">

          {signal_block()}
          {pattern_block()}
          {gap_block()}
          {inference_block()}

          <!-- CTA -->
          <div style="margin:40px 0;text-align:center">
            <a href="{APP_URL}/dashboard"
               style="display:inline-block;padding:12px 28px;background:#f59e0b;color:#000;
                      font-size:14px;font-weight:600;text-decoration:none;border-radius:6px">
              Open full briefing →
            </a>
          </div>

          <!-- Footer -->
          <hr style="border:none;border-top:1px solid #1a1814;margin:0 0 16px">
          <p style="margin:0;font-size:11px;color:#3a3733;font-family:monospace">
            Vello · <a href="{APP_URL}/settings" style="color:#3a3733">manage briefings</a>
          </p>

        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_briefing(user_id: str, email: str) -> bool:
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping briefing for %s", email)
        return False

    data = _get_briefing_data(user_id)
    date_str = datetime.now(timezone.utc).strftime("%A, %B %-d")
    html = _render_html(data, date_str)

    resend.api_key = RESEND_API_KEY
    try:
        resend.Emails.send({
            "from":    BRIEFING_FROM,
            "to":      [email],
            "subject": f"Vello · {date_str}",
            "html":    html,
        })
        return True
    except Exception as exc:
        log.error("Resend error for %s: %s", email, exc)
        return False


def send_all_briefings() -> None:
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, email, briefing_hour FROM users WHERE briefing_enabled=1"
    ).fetchall()
    conn.close()

    current_hour = datetime.now(timezone.utc).hour
    for row in rows:
        if row["briefing_hour"] == current_hour:
            try:
                send_briefing(row["id"], row["email"])
            except Exception as exc:
                log.error("Briefing failed for %s: %s", row["email"], exc)
