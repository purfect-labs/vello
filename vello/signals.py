"""
Intent-signal monitoring for Vello.

The scanner reads new text (from Kortex import, dialogue, or location events)
and matches it against the signal library. Matched signals become pending
triggers that surface on the user's dashboard.

Signal chaining: when a high-probability life transition fires, related signals
are placed on "watch" — their deduplication window is bypassed so they surface
immediately when detected, rather than being blocked by normal anti-fatigue logic.
"""
import re
from typing import Optional

# ── Signal library ─────────────────────────────────────────────────────────────

SIGNAL_LIBRARY = [
    {
        "id":              "travel_planned",
        "patterns":        [r"\bflight\b", r"\bhotel\b", r"\btrip to\b", r"\btravell?ing\b",
                            r"\bbooked.{0,20}(flight|hotel|ticket)\b", r"\bgoing to\b.{0,30}\b(week|month)\b"],
        "label":           "Travel planned",
        "priority":        "high",
        "action_type":     "travel_prep",
        "trigger_message": "Looks like you're planning a trip. Want me to help prep — packing reminders, home security check, partner heads-up?",
        "decay_hours":     72,
    },
    {
        "id":              "job_change",
        "patterns":        [r"\bnew job\b", r"\bstarting at\b", r"\baccepted.{0,15}offer\b",
                            r"\bfirst day\b.{0,20}\b(at|with)\b", r"\bresigning\b", r"\bleft.{0,10}job\b",
                            r"\bgot.{0,10}(position|role|job)\b"],
        "label":           "Job transition",
        "priority":        "high",
        "action_type":     "schedule_update",
        "trigger_message": "Sounds like there's a job change coming. Want me to update your commute zone, work hours, and daily schedule?",
        "decay_hours":     96,
    },
    {
        "id":              "moving_home",
        "patterns":        [r"\bmoving (to|out|in)\b", r"\bnew (apartment|flat|house|place)\b",
                            r"\blease starts\b", r"\bsigned.{0,10}lease\b"],
        "label":           "Moving",
        "priority":        "high",
        "action_type":     "home_update",
        "trigger_message": "Sounds like you're moving. Want me to update your home zone and reset location-based routines?",
        "decay_hours":     96,
    },
    {
        "id":              "relationship_change",
        "patterns":        [r"\b(we |i |)broke up\b", r"\bseparated\b", r"\bdivorced?\b",
                            r"\bgetting married\b", r"\bengaged\b", r"\bnew (partner|girlfriend|boyfriend)\b"],
        "label":           "Relationship change",
        "priority":        "medium",
        "action_type":     "contact_update",
        "trigger_message": "It sounds like your relationship situation may have changed. I can update your contacts and notification settings when you're ready.",
        "decay_hours":     48,
    },
    {
        "id":              "health_event",
        "patterns":        [r"\bsurgery\b", r"\bhospital\b", r"\brecovering\b",
                            r"\bdoctor (said|told)\b", r"\bdiagnosed with\b",
                            r"\bstarting (medication|meds|treatment)\b"],
        "label":           "Health event",
        "priority":        "medium",
        "action_type":     "routine_adjust",
        "trigger_message": "I noticed you mentioned a health situation. Want me to adjust your routines and workout reminders to account for recovery?",
        "decay_hours":     48,
    },
    {
        "id":              "financial_shift",
        "patterns":        [r"\btight on (money|cash|funds)\b", r"\bcutting back\b",
                            r"\bcan'?t afford\b", r"\bsaving (for|up)\b",
                            r"\bbig (purchase|expense|bill)\b"],
        "label":           "Financial change",
        "priority":        "low",
        "action_type":     "finance_adjust",
        "trigger_message": "I noticed some financial context. Want me to tighten auto-spend limits or flag any upcoming recurring charges?",
        "decay_hours":     24,
    },
    {
        "id":              "schedule_disruption",
        "patterns":        [r"\bworking late\b", r"\bovertime\b", r"\bcan'?t make it\b",
                            r"\bmissing.{0,10}(gym|workout|class)\b",
                            r"\bpushed back\b", r"\brescheduling\b"],
        "label":           "Schedule disruption",
        "priority":        "high",
        "action_type":     "schedule_adjust",
        "trigger_message": "Your schedule looks disrupted today. Want me to reschedule anything — gym session, reminders, partner notification?",
        "decay_hours":     6,
    },
    {
        "id":              "large_purchase",
        "patterns":        [r"\bordered.{0,20}\$?\d{3,}\b", r"\bbought.{0,20}(car|truck|bike|laptop|phone)\b",
                            r"\bpurchased\b.{0,30}\bfor\s+\$?\d{3,}\b"],
        "label":           "Large purchase",
        "priority":        "low",
        "action_type":     "finance_note",
        "trigger_message": "Looks like there was a significant purchase. Want me to log it against your budget context?",
        "decay_hours":     24,
    },
]

# Compile patterns once at import time
_COMPILED = [
    {**s, "_compiled": [re.compile(p, re.IGNORECASE) for p in s["patterns"]]}
    for s in SIGNAL_LIBRARY
]

_LIBRARY_MAP = {s["id"]: s for s in SIGNAL_LIBRARY}


# ── Signal transition graph (chaining) ────────────────────────────────────────
# When signal X fires, activate watches on related signals Y.
# watch_hours: how long to maintain the elevated watch window.
# factor: 0 = always fire (bypass dedup), 0.5 = half the normal dedup window.

SIGNAL_TRANSITIONS: dict[str, list[dict]] = {
    "job_change": [
        {"signal_id": "moving_home",         "watch_hours": 45 * 24, "factor": 0.0},
        {"signal_id": "schedule_disruption", "watch_hours":  7 * 24, "factor": 0.0},
        {"signal_id": "financial_shift",     "watch_hours": 60 * 24, "factor": 0.5},
    ],
    "moving_home": [
        {"signal_id": "financial_shift",     "watch_hours": 30 * 24, "factor": 0.5},
        {"signal_id": "schedule_disruption", "watch_hours":  3 * 24, "factor": 0.0},
    ],
    "relationship_change": [
        {"signal_id": "moving_home",         "watch_hours": 90 * 24, "factor": 0.0},
        {"signal_id": "financial_shift",     "watch_hours": 30 * 24, "factor": 0.5},
        {"signal_id": "schedule_disruption", "watch_hours":  7 * 24, "factor": 0.5},
    ],
    "health_event": [
        {"signal_id": "schedule_disruption", "watch_hours": 14 * 24, "factor": 0.0},
        {"signal_id": "financial_shift",     "watch_hours": 30 * 24, "factor": 0.5},
    ],
    "large_purchase": [
        {"signal_id": "financial_shift",     "watch_hours": 14 * 24, "factor": 0.0},
    ],
}


def scan_text(text: str) -> list[dict]:
    """
    Scan text and return list of matched signals (id, label, priority, trigger_message).
    Does NOT persist anything — caller decides what to do with matches.
    """
    if not text or not text.strip():
        return []

    matched = []
    for signal in _COMPILED:
        if any(p.search(text) for p in signal["_compiled"]):
            matched.append({
                "signal_id":       signal["id"],
                "label":           signal["label"],
                "priority":        signal["priority"],
                "action_type":     signal["action_type"],
                "trigger_message": signal["trigger_message"],
                "decay_hours":     signal["decay_hours"],
            })
    return matched


def get_signal_by_id(signal_id: str) -> Optional[dict]:
    return _LIBRARY_MAP.get(signal_id)


def get_transitions_for(signal_id: str) -> list[dict]:
    """Return the list of downstream watches to activate when signal_id fires."""
    return SIGNAL_TRANSITIONS.get(signal_id, [])


def fire_signals(user_id: str, text: str) -> int:
    """
    Scan text, create triggers respecting dedup + watches, activate downstream watches.
    Returns count of newly-created triggers.
    """
    if not text or not text.strip():
        return 0

    from vello.database import (
        has_active_trigger, get_active_watch,
        create_signal_trigger, create_signal_watch,
    )

    fired = 0
    for match in scan_text(text):
        sid = match["signal_id"]
        watch = get_active_watch(user_id, sid)

        if has_active_trigger(user_id, sid):
            if watch is None or watch["factor"] > 0:
                continue

        create_signal_trigger(
            user_id=user_id,
            signal_id=sid,
            label=match["label"],
            priority=match["priority"],
            action_type=match["action_type"],
            trigger_message=match["trigger_message"],
            source_text=text[:500],
            decay_hours=match["decay_hours"],
        )
        fired += 1

        for transition in get_transitions_for(sid):
            create_signal_watch(
                user_id=user_id,
                watched_signal_id=transition["signal_id"],
                triggered_by=sid,
                factor=transition["factor"],
                watch_hours=transition["watch_hours"],
            )

    return fired
