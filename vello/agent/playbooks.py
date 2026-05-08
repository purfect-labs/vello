"""
Playbook runtime + builtin definitions.

A playbook is a JSON recipe the planner prefers over ad-hoc reasoning for
known recurring tasks. The agent loop is told "if a matching playbook
exists, run its steps; deviate only when context demands it."

This module:
  - Defines the six builtin playbooks (seeded into the DB on first call)
  - Provides `seed_builtins()` called by the scheduler or startup
  - Provides `find_for_trigger()` to look up which playbook (if any)
    a trigger should invoke

Playbook definition_json shape:
  {
    "trigger": {"kind": "cron" | "signal" | ...},
    "steps": [
      {"tool": "...", "args": {...}},              # deterministic tool call
      {"tool": "...", "args_from_plan": true},     # args filled in by LLM
      {"plan": "..."},                             # free-form LLM directive
    ],
    "success_criteria": "..."
  }
"""
from __future__ import annotations

import logging
from typing import Optional

from vello import database as db

log = logging.getLogger(__name__)


# ── Builtin playbook definitions ─────────────────────────────────────────────

BUILTINS: list[dict] = [
    {
        "slug":  "weekly_planning",
        "title": "Weekly Planning",
        "definition": {
            "trigger": {"kind": ["weekly_planning", "playbook_manual"]},
            "description": (
                "Sunday evening: scan inventory, review next week's calendar, "
                "check weather, then draft a grocery list and family schedule "
                "summary. Drafts the grocery list as a list modification; "
                "sends a summary to household partner if channels allow."
            ),
            "steps": [
                {"tool": "read_inventory", "args": {"low_stock": True}},
                {"tool": "read_calendar", "args": {"window_hours": 168}},
                {"tool": "read_weather", "args": {"days": 7}},
                {"tool": "read_lists", "args": {"slug": "grocery"}},
                {"tool": "read_household_members", "args": {}},
                {
                    "plan": (
                        "Using the low-stock inventory items, upcoming calendar events, "
                        "weather, and current grocery list: (1) add missing staples to the "
                        "grocery list, (2) if there are events with guests or meals inferred, "
                        "add those ingredients too, (3) draft a short family schedule summary "
                        "for the week as a send_sms draft to the household partner if present."
                    )
                },
            ],
            "success_criteria": "list_modified OR draft_created",
        },
    },
    {
        "slug":  "restock_check",
        "title": "Restock Check",
        "definition": {
            "trigger": {"kind": ["restock_needed", "inventory_decay_scan"]},
            "description": (
                "Fired when an inventory item crosses its low-threshold. "
                "Checks whether the item is already on the grocery list; if not, "
                "adds it. If the item has a restock_url, surfaces it as a draft note."
            ),
            "steps": [
                {"tool": "read_inventory", "args": {"low_stock": True}},
                {"tool": "read_lists", "args": {"slug": "grocery"}},
                {
                    "plan": (
                        "For each low-stock item not already on the grocery list, "
                        "add it with appropriate quantity. If an item has a restock_url, "
                        "log an observation with the URL so the user sees it."
                    )
                },
            ],
            "success_criteria": "list_modified",
        },
    },
    {
        "slug":  "vendor_visit_prep",
        "title": "Vendor Visit Prep",
        "definition": {
            "trigger": {"kind": ["home_event_soon", "morning_review"]},
            "description": (
                "24h before a service visit: confirm what needs to happen, "
                "set a reminder, check vendor contact details, draft a prep "
                "checklist as a note."
            ),
            "steps": [
                {"tool": "read_household_members", "args": {}},
                {"tool": "read_vendors", "args": {}},
                {"tool": "read_context", "args": {"domain": "home"}},
                {
                    "plan": (
                        "For any service visit within 24h: (1) schedule a reminder "
                        "1 hour before, (2) log an observation with prep notes (clear "
                        "access, materials needed, payment method), (3) draft an SMS "
                        "confirmation to the vendor if not yet confirmed."
                    )
                },
            ],
            "success_criteria": "reminder_scheduled OR draft_created",
        },
    },
    {
        "slug":  "delivery_inbound",
        "title": "Delivery Inbound",
        "definition": {
            "trigger": {"kind": ["webhook:delivery", "signal:large_purchase"]},
            "description": (
                "When a delivery is inbound: open a tracking campaign, "
                "schedule a delivery-day reminder, and update the campaign "
                "when delivered."
            ),
            "steps": [
                {
                    "plan": (
                        "Open a campaign to track this delivery. Use the tracking ID "
                        "from the trigger payload if present. Schedule a reminder for "
                        "the estimated delivery date. If the payload says 'delivered', "
                        "close any matching open campaign instead."
                    )
                },
            ],
            "success_criteria": "campaign_opened OR campaign_closed",
        },
    },
    {
        "slug":  "seasonal_switch",
        "title": "Seasonal Switch",
        "definition": {
            "trigger": {"kind": ["seasonal_switch", "playbook_manual"]},
            "description": (
                "Quarterly: open campaigns for HVAC service, garden transition, "
                "and wardrobe rotation. Check vendor records for HVAC/lawn contacts."
            ),
            "steps": [
                {"tool": "read_vendors", "args": {}},
                {"tool": "read_context", "args": {"domain": "home"}},
                {"tool": "read_open_campaigns", "args": {}},
                {
                    "plan": (
                        "Based on the current season (infer from date/weather if available): "
                        "(1) if no open HVAC campaign, open one with intent "
                        "'schedule_hvac_service' and set a watcher for hvac-related "
                        "vendor messages, (2) add seasonal tasks to weekly_errands list, "
                        "(3) if a relevant vendor is in the record, draft a service request."
                    )
                },
            ],
            "success_criteria": "campaign_opened OR draft_created",
        },
    },
    {
        "slug":  "guest_arrival",
        "title": "Guest Arrival Prep",
        "definition": {
            "trigger": {"kind": ["playbook_manual"]},
            "description": (
                "Manually triggered with arrival dates + headcount. "
                "Preps groceries, cleaning schedule, room assignments, "
                "and optional vendor bookings (cleaner, etc.)."
            ),
            "steps": [
                {"tool": "read_inventory", "args": {"low_stock": True}},
                {"tool": "read_lists", "args": {"slug": "grocery"}},
                {"tool": "read_vendors", "args": {"kind": "cleaner"}},
                {"tool": "read_household_members", "args": {}},
                {
                    "plan": (
                        "Using the trigger payload (arrival_date, departure_date, "
                        "guest_count, guest_names if given): "
                        "(1) add guest-appropriate grocery items, "
                        "(2) if cleaner vendor exists, draft a service request for the "
                        "day before arrival, "
                        "(3) open a campaign 'guest_visit_[names]' that expires after "
                        "the departure date, "
                        "(4) schedule a reminder the morning of arrival."
                    )
                },
            ],
            "success_criteria": "list_modified AND (campaign_opened OR draft_created)",
        },
    },
]


def seed_builtins() -> None:
    """Idempotent — safe to call on every startup."""
    for pb in BUILTINS:
        try:
            db.upsert_playbook(
                household_id=None,
                slug=pb["slug"],
                title=pb["title"],
                definition=pb["definition"],
                source="builtin",
                confidence=1.0,
            )
        except Exception as exc:
            log.warning("failed to seed playbook %s: %s", pb["slug"], exc)


def find_for_trigger(trigger_kind: str, household_id: Optional[str]) -> Optional[dict]:
    """
    Return the best-matching enabled playbook for a trigger kind, or None.
    Household-specific playbooks take precedence over global (NULL household_id) ones.
    """
    rows = db.list_playbooks(household_id=household_id, enabled_only=True)
    for row in rows:
        defn = {}
        try:
            import json
            defn = json.loads(row["definition_json"] or "{}")
        except (ValueError, TypeError):
            continue
        trigger_spec = defn.get("trigger") or {}
        kind_spec = trigger_spec.get("kind")
        if kind_spec is None:
            continue
        if isinstance(kind_spec, str) and kind_spec == trigger_kind:
            return dict(row)
        if isinstance(kind_spec, list) and trigger_kind in kind_spec:
            return dict(row)
    return None
