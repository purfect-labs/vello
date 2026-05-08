"""
Working-memory builder.

The planner's prompt budget is a real constraint. Instead of dumping
everything Vello knows, this module assembles a *trigger-conditioned slice*:
different triggers retrieve different things, with failures over-weighted
so the planner sees the patterns that matter.

Output shape: a single string, formatted with section headers, ready to be
stuffed into the planner's first user message. We use plain text rather
than JSON because Claude planners track structure better when sections are
labelled and data is rendered as bullet-y prose.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from vello import database as db

log = logging.getLogger(__name__)


# Token budget allowances per slice (lines, roughly — 1 line ≈ 25-30 tokens).
_BUDGETS = {
    "context":      30,
    "members":      20,
    "lists":        25,
    "inventory":    20,
    "events":       20,
    "campaigns":    10,
    "patterns":     15,
    "recent":       15,
    "world":        20,
}


def build_working_memory(
    user_id: str,
    household_id: Optional[str],
    trigger_kind: str,
    trigger_payload: Optional[dict] = None,
    open_campaign_id: Optional[str] = None,
) -> str:
    """
    Assemble the working-memory string. The shape depends on trigger_kind —
    a `morning_review` retrieves broad household state; a `webhook:delivery`
    retrieves only the slice relevant to deliveries + the originating
    package.

    Returns "" gracefully if the user has no household yet (cold start).
    """
    sections: list[str] = []
    weights = _trigger_weights(trigger_kind)

    if weights["members"] and household_id:
        sections.append(_render_members(household_id))
    if weights["context"]:
        sections.append(_render_context(user_id, trigger_kind))
    if weights["world"] and household_id:
        sections.append(_render_world(household_id))
    if weights["inventory"] and household_id:
        sections.append(_render_inventory(household_id, low_only=weights["inventory_low_only"]))
    if weights["lists"] and household_id:
        sections.append(_render_lists(household_id))
    if weights["events"] and household_id:
        sections.append(_render_events(household_id, hours=weights["events_hours"]))
    if weights["campaigns"]:
        sections.append(_render_campaigns(user_id, exclude_id=open_campaign_id))
    if weights["patterns"]:
        sections.append(_render_patterns(user_id))
    if weights["recent"]:
        sections.append(_render_recent_actions(user_id))
    if weights["dialogue"]:
        sections.append(_render_recent_dialogue(user_id))

    # Failure-aware: surface the last few errors regardless of trigger kind,
    # so the planner sees what just went wrong before re-trying.
    sections.append(_render_recent_failures(user_id))

    # Strip empties, join with blank lines between sections.
    return "\n\n".join(s for s in sections if s).strip()


# ── Trigger → slice weights ──────────────────────────────────────────────────
#
# weights are not strict — they tell the renderer whether to include a slice
# at all. Per-slice token budgets in `_BUDGETS` cap line counts.

def _trigger_weights(trigger_kind: str) -> dict:
    base = {
        "context":           True,
        "members":           True,
        "world":             True,
        "lists":             True,
        "inventory":         True,
        "inventory_low_only": False,
        "events":            True,
        "events_hours":      72,
        "campaigns":         True,
        "patterns":          False,
        "recent":            True,
        "dialogue":          False,
    }
    if trigger_kind == "morning_review":
        base["events_hours"] = 24
        base["patterns"] = True
        base["inventory_low_only"] = True
    elif trigger_kind == "evening_review":
        base["events_hours"] = 36
        base["recent"] = True
        base["dialogue"] = True
    elif trigger_kind == "weekly_planning":
        base["events_hours"] = 24 * 7
        base["patterns"] = True
        base["dialogue"] = True
    elif trigger_kind in ("restock_needed", "inventory_decay_scan"):
        base["inventory_low_only"] = True
        base["world"] = False
        base["events"] = False
        base["patterns"] = False
        base["dialogue"] = False
    elif trigger_kind.startswith("webhook:") or trigger_kind.startswith("signal:"):
        base["world"] = False
        base["patterns"] = False
        base["events_hours"] = 48
    elif trigger_kind in ("user_request", "voice"):
        base["dialogue"] = True
        base["patterns"] = True
    elif trigger_kind == "campaign_resume":
        base["campaigns"] = True
        base["recent"] = True
        base["dialogue"] = True
    return base


# ── Renderers ────────────────────────────────────────────────────────────────

def _render_section(label: str, lines: list[str]) -> str:
    if not lines:
        return f"[{label}] (none)"
    body = "\n".join(f"- {ln}" for ln in lines)
    return f"[{label}]\n{body}"


def _render_context(user_id: str, trigger_kind: str) -> str:
    rows = db.get_context(user_id)
    if not rows:
        return _render_section("CONTEXT", [])

    # Preference: home + people + preferences domains first; everything else
    # second. For non-home triggers we still include home but down-rank.
    def rank(r) -> tuple[int, str]:
        d = r["domain"]
        primary = ("home", "people", "preferences", "schedule")
        return (primary.index(d) if d in primary else len(primary), d)

    rows_sorted = sorted(rows, key=rank)[: _BUDGETS["context"]]
    lines = [f"{r['domain']}.{r['key']} = {_truncate(r['value'], 80)}  ({r['source']})"
             for r in rows_sorted]
    return _render_section("CONTEXT", lines)


def _render_members(household_id: str) -> str:
    rows = db.list_household_members(household_id)
    if not rows:
        return _render_section("HOUSEHOLD_MEMBERS", [])
    lines = []
    for r in rows[: _BUDGETS["members"]]:
        try:
            ch = json.loads(r["channels_json"] or "{}")
            cs = json.loads(r["consent_json"] or "{}")
        except (ValueError, TypeError):
            ch, cs = {}, {}
        chan = ", ".join(f"{k}={v}" for k, v in ch.items() if v) or "(no channels)"
        notify = "notify=ok" if cs.get("notify") else "notify=blocked"
        lines.append(
            f"id={r['id']} name={r['name']} kind={r['kind']} "
            f"rel={r['relationship'] or '-'} {chan} {notify}"
        )
    return _render_section("HOUSEHOLD_MEMBERS", lines)


def _render_world(household_id: str) -> str:
    """Compact graph rendering: list entities by kind, then key relations."""
    entities = db.list_home_entities(household_id)
    if not entities:
        return _render_section("WORLD_MODEL", [])
    by_kind: dict[str, list[str]] = {}
    for e in entities:
        by_kind.setdefault(e["kind"], []).append(f"{e['label']}#{e['id']}")
    relations = db.query_home_relations(household_id)
    rel_lines = []
    for r in relations[:10]:
        rel_lines.append(f"{r['src_entity_id']} —{r['predicate']}→ {r['dst_entity_id']}")
    lines = []
    for kind, labels in by_kind.items():
        lines.append(f"{kind}s: {', '.join(labels[:8])}")
    if rel_lines:
        lines.append("relations:")
        lines.extend(f"  {ln}" for ln in rel_lines)
    return _render_section("WORLD_MODEL", lines[: _BUDGETS["world"]])


def _render_inventory(household_id: str, low_only: bool) -> str:
    rows = db.list_inventory(household_id, low_stock_only=low_only)
    if not rows:
        label = "INVENTORY_LOW_STOCK" if low_only else "INVENTORY"
        return _render_section(label, [])
    lines = []
    for r in rows[: _BUDGETS["inventory"]]:
        last = r["last_used_at"] or "never"
        lt = r["est_lifetime_days"]
        lines.append(
            f"id={r['id']} {r['label']} last_used={last} "
            f"lifetime={lt or '-'}d"
        )
    label = "INVENTORY_LOW_STOCK" if low_only else "INVENTORY"
    return _render_section(label, lines)


def _render_lists(household_id: str) -> str:
    lists = db.list_lists(household_id)
    if not lists:
        return _render_section("LISTS", [])
    lines = []
    for l in lists:
        items = db.list_items_for_list(l["id"], status="open")
        item_summary = ", ".join(
            f"{it['label']}{('×'+it['qty']) if it['qty'] else ''}"
            for it in items[:6]
        ) or "(empty)"
        if len(items) > 6:
            item_summary += f", … +{len(items) - 6} more"
        lines.append(f"{l['slug']} (id={l['id']}): {item_summary}")
    return _render_section("LISTS", lines[: _BUDGETS["lists"]])


def _render_events(household_id: str, hours: int) -> str:
    rows = db.list_home_events(household_id, window_hours=hours)
    if not rows:
        return _render_section(f"EVENTS_NEXT_{hours}H", [])
    lines = [f"{r['when_at']} — {r['title']} ({r['kind']})" for r in rows[: _BUDGETS["events"]]]
    return _render_section(f"EVENTS_NEXT_{hours}H", lines)


def _render_campaigns(user_id: str, exclude_id: Optional[str]) -> str:
    rows = db.list_open_campaigns(user_id)
    rows = [r for r in rows if r["id"] != exclude_id]
    if not rows:
        return _render_section("OTHER_OPEN_CAMPAIGNS", [])
    lines = [
        f"id={r['id']} intent={r['intent']} expires={r['expires_at']} "
        f"summary={_truncate(r['summary'] or '-', 80)}"
        for r in rows[: _BUDGETS["campaigns"]]
    ]
    return _render_section("OTHER_OPEN_CAMPAIGNS", lines)


def _render_patterns(user_id: str) -> str:
    rows = db.get_temporal_patterns(user_id)
    if not rows:
        return _render_section("TEMPORAL_PATTERNS", [])
    lines = []
    for r in rows[: _BUDGETS["patterns"]]:
        if (r["sample_count"] or 0) < 3:
            continue
        mean = r["mean_minutes"]
        if mean is None:
            continue
        h, m = divmod(int(mean), 60)
        lines.append(f"{r['pattern_key']} ≈ {h:02d}:{m:02d} (n={r['sample_count']})")
    return _render_section("TEMPORAL_PATTERNS", lines)


def _render_recent_actions(user_id: str) -> str:
    rows = db.get_recent_tool_calls(user_id, minutes=24 * 60, limit=_BUDGETS["recent"])
    if not rows:
        return _render_section("RECENT_ACTIONS_24H", [])
    lines = []
    for r in rows:
        marker = "✗" if r["error_text"] else ("→" if r["approval"] == "auto" else "·")
        lines.append(f"{marker} {r['tool_name']} approval={r['approval']} at={r['executed_at']}")
    return _render_section("RECENT_ACTIONS_24H", lines)


def _render_recent_failures(user_id: str) -> str:
    """
    Failure-weighted slice. Shows up to 5 most-recent erroring tool calls
    even when they're already in RECENT_ACTIONS_24H — repetition is the
    point: planners adapt to errors only when they're salient.
    """
    rows = db.get_recent_tool_calls(user_id, minutes=24 * 60, limit=50)
    fails = [r for r in rows if r["error_text"]]
    if not fails:
        return ""
    fails = fails[:5]
    lines = [
        f"{r['tool_name']} → {_truncate(r['error_text'], 100)} (at {r['executed_at']})"
        for r in fails
    ]
    return _render_section("RECENT_FAILURES", lines)


def _render_recent_dialogue(user_id: str) -> str:
    rows = db.get_dialogue_history(user_id, limit=8)
    if not rows:
        return _render_section("RECENT_DIALOGUE", [])
    lines = [f"{r['role']}: {_truncate(r['content'], 120)}" for r in rows]
    return _render_section("RECENT_DIALOGUE", lines)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _truncate(s: Optional[str], n: int) -> str:
    if s is None:
        return ""
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


# ── Presence ─────────────────────────────────────────────────────────────────

def build_presence(user_id: str, household_id: Optional[str]) -> dict:
    """
    Coarse presence inference. Used by the approval engine to gate notifications.
    Returns:
      home_members: list of member_ids most likely at home (from latest
                    location_event "enter" with no later "exit").
      dnd_until:    iso timestamp if the user has a quiet-hours policy active.
      current_local_hour: int 0-23 in user's tz.
    """
    presence = {
        "home_members":       [],
        "dnd_until":          None,
        "current_local_hour": None,
    }
    user = db.get_user_by_id(user_id)
    if not user:
        return presence

    tz_name = user["timezone"] if "timezone" in user.keys() else "UTC"
    try:
        from zoneinfo import ZoneInfo
        local_now = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_name))
        presence["current_local_hour"] = local_now.hour
    except Exception:
        presence["current_local_hour"] = datetime.now(timezone.utc).hour

    # DND derived from morning_hour (defaults 7) and evening_hour (default 21)
    # via user policy. Outside [morning, evening] is DND for notification path.
    policy = db.get_user_policy(user_id)
    morning = int(policy.get("morning_hour", 7))
    evening = int(policy.get("evening_hour", 21))
    hour = presence["current_local_hour"] or 0
    if hour < morning or hour >= evening:
        # DND active — flag with a coarse retry timestamp at next morning_hour.
        try:
            from zoneinfo import ZoneInfo
            now_local = datetime.now(timezone.utc).astimezone(ZoneInfo(tz_name))
            target = now_local.replace(hour=morning, minute=0, second=0, microsecond=0)
            if hour >= evening:
                target = target + timedelta(days=1)
            presence["dnd_until"] = target.astimezone(timezone.utc).isoformat()
        except Exception:
            presence["dnd_until"] = (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()

    return presence
