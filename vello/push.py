"""
Web Push notification dispatcher.

Uses VAPID (Voluntary Application Server Identification) via pywebpush.
The server generates a VAPID key pair once; the public key is served to the
frontend so the browser can create a push subscription bound to this server.

When VAPID_PRIVATE_KEY is absent, all push calls silently no-op so existing
functionality is unaffected (daily email briefing stays the primary path).

Push is fired for:
  - New draft created (agent wants to act)
  - Temporal deviation (running late alert)
  - Morning review completion with drafts
  - Explicit notification from agent tool (future)
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from vello.config import VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, VAPID_SUBJECT

log = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY)


def send_push(endpoint: str, p256dh: str, auth: str,
              title: str, body: str,
              url: str = "/home",
              tag: Optional[str] = None) -> bool:
    """
    Send a single web push notification. Returns True on success, False on
    failure (caller decides whether to remove the subscription).

    All exceptions are caught — push failure must never kill an agent turn.
    """
    if not _is_configured():
        return False

    payload = json.dumps({
        "title": title,
        "body":  body,
        "url":   url,
        "tag":   tag or str(uuid.uuid4()),
    })

    try:
        from pywebpush import webpush, WebPushException
        subscription_info = {
            "endpoint": endpoint,
            "keys": {"p256dh": p256dh, "auth": auth},
        }
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except Exception as exc:
        # 410 Gone = subscription expired; caller should delete it.
        log.debug("push failed for endpoint %s: %s", endpoint[:40], exc)
        return False


def send_to_user(user_id: str, title: str, body: str,
                  url: str = "/home", tag: Optional[str] = None) -> int:
    """
    Send a push to all active subscriptions for the user.
    Returns count of successful deliveries. Removes expired subscriptions (410).
    """
    if not _is_configured():
        return 0

    from vello import database as db
    conn = db.get_connection()
    subs = conn.execute(
        "SELECT * FROM push_subscriptions WHERE user_id=?", (user_id,)
    ).fetchall()
    conn.close()

    sent = 0
    expired_ids = []
    for sub in subs:
        ok = send_push(
            endpoint=sub["endpoint"],
            p256dh=sub["p256dh"],
            auth=sub["auth"],
            title=title,
            body=body,
            url=url,
            tag=tag,
        )
        if ok:
            sent += 1
        else:
            # Assume expired — remove it so we stop retrying
            expired_ids.append(sub["id"])

    if expired_ids:
        conn = db.get_connection()
        with conn:
            conn.execute(
                f"DELETE FROM push_subscriptions WHERE id IN ({','.join('?'*len(expired_ids))})",
                tuple(expired_ids),
            )
        conn.close()

    return sent


def notify_new_draft(user_id: str, tool_name: str, summary: str) -> None:
    """Fire a push when the agent creates a new draft needing user action."""
    send_to_user(
        user_id,
        title="Vello wants to do something",
        body=summary[:120],
        url="/home",
        tag=f"draft_{tool_name}",
    )


def notify_temporal_deviation(user_id: str, pattern_key: str, message: str) -> None:
    """Temporal deviation alert — user is running late vs their pattern."""
    send_to_user(
        user_id,
        title=f"Running late — {pattern_key.replace('_', ' ')}",
        body=message[:120],
        url="/home",
        tag=f"temporal_{pattern_key}",
    )
