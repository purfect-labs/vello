"""
Campaign matching — the "is there an open standing intent that this trigger
advances?" check that runs at the start of every agent turn.

A campaign's `watcher_json` is a small predicate object like:

  {"trigger_kind": "webhook:delivery", "tracking_id": "1Z..."}
  {"trigger_kind": "user_request", "intent_keywords": ["hvac","schedule"]}
  {"trigger_kind": ["morning_review", "weekly_planning"]}

Match rules:
  - "trigger_kind" can be a string (exact) or list (membership)
  - "intent_keywords": every keyword must appear in the trigger payload's
    text fields (case-insensitive substring)
  - other keys: equality match against trigger_payload's flat keys

If multiple campaigns match, the most-recently-touched one wins. (A future
ranker can override this — e.g. priority field — but the simple recency
rule is right for MVP.)

Why: most home work is multi-day. Without resume, every cron tick starts
from zero and nothing actually progresses. With resume, opening
"schedule_hvac_before_oct" once means it gets revisited on every relevant
tick until done — exactly how a human assistant would track it.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from vello import database as db

log = logging.getLogger(__name__)


def find_matching_open(
    user_id: str,
    trigger_kind: str,
    trigger_payload: Optional[dict] = None,
):
    """
    Returns the matching campaign row (sqlite Row) or None. Most-recent wins.
    """
    payload = trigger_payload or {}
    candidates: list[tuple] = []  # (matched, row)

    for row in db.list_open_campaigns(user_id):
        try:
            watcher = json.loads(row["watcher_json"] or "{}") or {}
        except (ValueError, TypeError):
            continue
        if _matches(watcher, trigger_kind, payload):
            candidates.append(row)

    if not candidates:
        return None
    # most-recently created; for MVP this proxies "most active". A future
    # heuristic could weight by step count, recency of last step, etc.
    candidates.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return candidates[0]


def _matches(watcher: dict, trigger_kind: str, payload: dict) -> bool:
    if not watcher:
        return False

    # trigger_kind constraint
    tk = watcher.get("trigger_kind")
    if tk is not None:
        if isinstance(tk, str) and tk != trigger_kind:
            return False
        if isinstance(tk, list) and trigger_kind not in tk:
            return False

    # keyword constraint over freeform text fields
    keywords = watcher.get("intent_keywords") or []
    if keywords:
        haystack = _flatten_text(payload).lower()
        for kw in keywords:
            if str(kw).lower() not in haystack:
                return False

    # remaining keys: equality match against payload[k]
    reserved = {"trigger_kind", "intent_keywords"}
    for k, v in watcher.items():
        if k in reserved:
            continue
        if k not in payload:
            return False
        if payload[k] != v:
            return False

    return True


def _flatten_text(payload: dict) -> str:
    parts: list[str] = []
    for v in payload.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (list, tuple)):
            parts.extend(str(x) for x in v if isinstance(x, (str, int, float)))
        elif isinstance(v, dict):
            parts.append(_flatten_text(v))
    return " ".join(parts)


# ── Convenience wrappers exposed for routes / tests ─────────────────────────

def open_for_user(user_id: str) -> list[dict]:
    return [
        {
            "id":         r["id"],
            "intent":     r["intent"],
            "summary":    r["summary"],
            "status":     r["status"],
            "expires_at": r["expires_at"],
            "created_at": r["created_at"],
        }
        for r in db.list_open_campaigns(user_id)
    ]


def render_summary(row) -> str:
    """One-line render for inclusion in working memory."""
    if not row:
        return ""
    return (
        f"intent={row['intent']} expires={row['expires_at']} "
        f"created={row['created_at']} summary={row['summary'] or '-'}"
    )
