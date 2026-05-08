"""
Tool catalog + dispatcher.

Each tool is a `Tool` dataclass:
  name        — identifier the planner uses
  description — sentence the planner sees
  input_schema — JSON Schema (Anthropic tool-use shape)
  tier        — 1: read; 2: internal write; 3: external (drafts by default);
                4: irreversible (always confirm)
  data_class  — internal | third_party | kortex (used by privacy controls)
  executor    — callable(user_id, args, ctx) → result dict; raise ToolError on failure

The executor receives a `ToolContext` carrying user_id, household_id, and a
session_id when run inside an agent loop. Tools that work outside the loop
(e.g. agent-trigger smoke tests) can pass a synthetic context.

Tier 3/4 tool stubs in this file return `{"unavailable": True, ...}` until the
MVP-3 integrations land. The agent loop's approval engine still drafts them
correctly — the tool just can't auto-execute.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from vello import database as db

log = logging.getLogger(__name__)


# ── Errors & context ─────────────────────────────────────────────────────────

class ToolError(Exception):
    """Raised by an executor when execution fails. Caught by the agent loop."""

class ToolUnavailable(ToolError):
    """Raised when a tool exists but cannot run right now (missing API key,
    integration disabled, OAuth expired). Loop converts to an `unavailable`
    observation so the planner re-plans rather than retrying."""

class ToolValidationError(ToolError):
    """Raised when args fail schema validation. Loop retries the planner once
    with the error feedback before giving up."""


@dataclass
class ToolContext:
    user_id:      str
    household_id: Optional[str] = None
    session_id:   Optional[str] = None


@dataclass
class Tool:
    name:         str
    description:  str
    input_schema: dict
    tier:         int
    data_class:   str                                       # internal | third_party | kortex
    executor:     Callable[[ToolContext, dict], dict]
    cost_usd:     float = 0.0                               # per-call estimate, for budget engine


# ── Registry ─────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    if tool.name in _REGISTRY:
        log.warning("tool registered twice: %s", tool.name)
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> Optional[Tool]:
    return _REGISTRY.get(name)


def get_tools(user_id: Optional[str] = None) -> list[Tool]:
    """All registered tools. Filtering by user policy happens in `for_planner`."""
    return list(_REGISTRY.values())


def for_planner(user_id: str, allowed_data_classes: Optional[set[str]] = None) -> list[dict]:
    """
    Render the catalog into Anthropic tool-use shape. Filters out tools whose
    data_class the user has blocked.
    """
    out: list[dict] = []
    for tool in _REGISTRY.values():
        if allowed_data_classes is not None and tool.data_class not in allowed_data_classes:
            continue
        out.append({
            "name":         tool.name,
            "description":  tool.description,
            "input_schema": tool.input_schema,
        })
    return out


def dispatch(name: str, args: dict, ctx: ToolContext) -> dict:
    """Validate + execute. Raises ToolError subclasses on failure."""
    tool = _REGISTRY.get(name)
    if not tool:
        raise ToolValidationError(f"unknown tool: {name}")
    _validate_args(tool, args)
    return tool.executor(ctx, args)


# ── Lightweight JSON-schema validator ────────────────────────────────────────
#
# We don't pull in `jsonschema` for this — the schemas we use are small and a
# focused validator avoids an extra dependency in a hot path.

_PRIMITIVE_TYPES = {
    "string":  str,
    "integer": int,
    "number":  (int, float),
    "boolean": bool,
    "object":  dict,
    "array":   list,
    "null":    type(None),
}


def _validate_args(tool: Tool, args: dict) -> None:
    schema = tool.input_schema or {}
    if schema.get("type") and schema["type"] != "object":
        # Tool-use args are always objects in our convention.
        raise ToolValidationError(f"tool {tool.name}: expected object schema")
    if not isinstance(args, dict):
        raise ToolValidationError(f"tool {tool.name}: args must be an object")

    required = schema.get("required") or []
    props = schema.get("properties") or {}

    missing = [k for k in required if k not in args]
    if missing:
        raise ToolValidationError(
            f"tool {tool.name}: missing required arg(s): {', '.join(missing)}"
        )

    for key, value in args.items():
        if key not in props:
            # Unknown keys are tolerated — Claude sometimes adds explanation
            # fields. We only enforce typed/declared properties.
            continue
        spec = props[key]
        _check_property(tool.name, key, value, spec)


def _check_property(tool_name: str, key: str, value: Any, spec: dict) -> None:
    expected = spec.get("type")
    if expected is None:
        return
    if isinstance(expected, list):
        types = tuple(_PRIMITIVE_TYPES[t] for t in expected if t in _PRIMITIVE_TYPES)
    else:
        types = _PRIMITIVE_TYPES.get(expected, ())
        if not isinstance(types, tuple):
            types = (types,)
    if types and not isinstance(value, types):
        raise ToolValidationError(
            f"tool {tool_name}: arg {key!r} expected {expected}, got {type(value).__name__}"
        )
    enum = spec.get("enum")
    if enum is not None and value not in enum:
        raise ToolValidationError(
            f"tool {tool_name}: arg {key!r} must be one of {enum}, got {value!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1 — read-only tools (always auto)
# ─────────────────────────────────────────────────────────────────────────────

def _exec_read_context(ctx: ToolContext, args: dict) -> dict:
    domain = args.get("domain")
    rows = db.get_context(ctx.user_id, domain=domain)
    out = [
        {"domain": r["domain"], "key": r["key"], "value": r["value"], "source": r["source"]}
        for r in rows
    ]
    if "key" in args and args["key"]:
        out = [r for r in out if r["key"] == args["key"]]
    return {"entries": out}


register(Tool(
    name="read_context",
    description=(
        "Read entries from the user's life_context store. Filter by domain "
        "(schedule|fitness|work|finance|health|home|people|preferences) and "
        "optionally by key. Use this before guessing user-stated facts."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "key":    {"type": "string"},
        },
    },
    tier=1, data_class="internal",
    executor=_exec_read_context,
))


def _exec_read_household_members(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        return {"members": []}
    rows = db.list_household_members(ctx.household_id)
    members = []
    for r in rows:
        try:
            channels = json.loads(r["channels_json"] or "{}")
        except (ValueError, TypeError):
            channels = {}
        try:
            consent = json.loads(r["consent_json"] or "{}")
        except (ValueError, TypeError):
            consent = {}
        members.append({
            "id":           r["id"],
            "kind":         r["kind"],
            "name":         r["name"],
            "relationship": r["relationship"],
            "channels":     channels,
            "consent":      consent,
        })
    return {"members": members}


register(Tool(
    name="read_household_members",
    description=(
        "List people, children, and pets in the household with their notify "
        "channels and consent flags. Use before any tool that targets a member."
    ),
    input_schema={"type": "object", "properties": {}},
    tier=1, data_class="internal",
    executor=_exec_read_household_members,
))


def _exec_read_member_preferences(ctx: ToolContext, args: dict) -> dict:
    member_id = args.get("member_id")
    if not member_id:
        return {"preferences": []}
    rows = db.list_member_preferences(member_id)
    return {
        "preferences": [
            {"domain": r["domain"], "key": r["key"], "value": r["value"], "source": r["source"]}
            for r in rows
        ]
    }


register(Tool(
    name="read_member_preferences",
    description="Read per-member preferences (allergies, dietary, sleep schedule, etc.).",
    input_schema={
        "type": "object",
        "properties": {"member_id": {"type": "string"}},
        "required": ["member_id"],
    },
    tier=1, data_class="internal",
    executor=_exec_read_member_preferences,
))


def _exec_read_vendors(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        return {"vendors": []}
    rows = db.list_vendors(ctx.household_id, kind=args.get("kind"))
    return {
        "vendors": [
            {"id": r["id"], "name": r["name"], "kind": r["kind"],
             "phone": r["phone"], "email": r["email"],
             "last_contacted_at": r["last_contacted_at"]}
            for r in rows
        ]
    }


register(Tool(
    name="read_vendors",
    description="List household vendors. Optionally filter by kind (handyman|plumber|hvac|...).",
    input_schema={
        "type": "object",
        "properties": {"kind": {"type": "string"}},
    },
    tier=1, data_class="internal",
    executor=_exec_read_vendors,
))


def _exec_read_lists(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        return {"lists": []}
    slug_filter = args.get("slug")
    lists = db.list_lists(ctx.household_id)
    out = []
    for l in lists:
        if slug_filter and l["slug"] != slug_filter:
            continue
        items = db.list_items_for_list(l["id"], status="open")
        out.append({
            "id":    l["id"],
            "slug":  l["slug"],
            "label": l["label"],
            "kind":  l["kind"],
            "open_items": [
                {"id": it["id"], "label": it["label"], "qty": it["qty"]}
                for it in items
            ],
        })
    return {"lists": out}


register(Tool(
    name="read_lists",
    description="Read household lists (groceries, hardware, etc.) with their open items.",
    input_schema={
        "type": "object",
        "properties": {"slug": {"type": "string"}},
    },
    tier=1, data_class="internal",
    executor=_exec_read_lists,
))


def _exec_read_inventory(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        return {"items": []}
    low_only = bool(args.get("low_stock", False))
    rows = db.list_inventory(ctx.household_id, low_stock_only=low_only)
    return {
        "items": [
            {"id": r["id"], "label": r["label"],
             "last_used_at": r["last_used_at"],
             "est_lifetime_days": r["est_lifetime_days"],
             "low_threshold_days": r["low_threshold_days"]}
            for r in rows
        ]
    }


register(Tool(
    name="read_inventory",
    description="Read inventory items. Pass low_stock=true to filter to running-low items.",
    input_schema={
        "type": "object",
        "properties": {"low_stock": {"type": "boolean"}},
    },
    tier=1, data_class="internal",
    executor=_exec_read_inventory,
))


def _exec_read_recent_actions(ctx: ToolContext, args: dict) -> dict:
    minutes = int(args.get("minutes", 1440))  # default 24h
    rows = db.get_recent_tool_calls(ctx.user_id, minutes=minutes, limit=20)
    return {
        "actions": [
            {"tool": r["tool_name"], "approval": r["approval"],
             "at": r["executed_at"], "error": r["error_text"]}
            for r in rows
        ]
    }


register(Tool(
    name="read_recent_actions",
    description="What did Vello recently do (or attempt) for this user. Useful before re-trying.",
    input_schema={
        "type": "object",
        "properties": {"minutes": {"type": "integer"}},
    },
    tier=1, data_class="internal",
    executor=_exec_read_recent_actions,
))


def _exec_read_temporal(ctx: ToolContext, args: dict) -> dict:
    key = args.get("key")
    if key:
        row = db.get_temporal_pattern(ctx.user_id, key)
        if not row:
            return {"pattern": None}
        return {"pattern": dict(row)}
    rows = db.get_temporal_patterns(ctx.user_id)
    return {"patterns": [dict(r) for r in rows]}


register(Tool(
    name="read_temporal",
    description=(
        "Read learned temporal patterns. Pass `key` for one (e.g. 'gym'); "
        "omit for all. Useful for anticipating routines."
    ),
    input_schema={
        "type": "object",
        "properties": {"key": {"type": "string"}},
    },
    tier=1, data_class="internal",
    executor=_exec_read_temporal,
))


def _exec_read_open_campaigns(ctx: ToolContext, args: dict) -> dict:
    rows = db.list_open_campaigns(ctx.user_id)
    return {
        "campaigns": [
            {"id": r["id"], "intent": r["intent"], "summary": r["summary"],
             "expires_at": r["expires_at"], "created_at": r["created_at"]}
            for r in rows
        ]
    }


register(Tool(
    name="read_open_campaigns",
    description="List standing intents Vello is currently tracking for this user.",
    input_schema={"type": "object", "properties": {}},
    tier=1, data_class="internal",
    executor=_exec_read_open_campaigns,
))


def _exec_query_world(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        return {"entities": [], "relations": []}
    kind = args.get("entity_kind")
    predicate = args.get("predicate")
    entities = []
    if kind or not predicate:
        entities = [
            dict(r) for r in db.list_home_entities(ctx.household_id, kind=kind)
        ]
    relations = []
    if predicate:
        relations = [
            dict(r) for r in db.query_home_relations(ctx.household_id, predicate=predicate)
        ]
    return {"entities": entities, "relations": relations}


register(Tool(
    name="query_world",
    description=(
        "Query the household world model. Either entity_kind (room|object|"
        "member|vendor|recurring_event) or a relation predicate. Useful for "
        "spatial / structural questions like 'what's in the kitchen'."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "entity_kind": {"type": "string"},
            "predicate":   {"type": "string"},
        },
    },
    tier=1, data_class="internal",
    executor=_exec_query_world,
))


# ── Tier 1 integration reads (third_party; return unavailable when no key) ───

def _exec_read_calendar(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.calendar import CalendarClient
    window = int(args.get("window_hours", 72))
    events = CalendarClient(ctx.user_id).list_events(window_hours=window)
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "google_calendar")
    return {"events": events}

register(Tool(
    name="read_calendar",
    description="Read the user's primary calendar for the next N hours.",
    input_schema={
        "type": "object",
        "properties": {"window_hours": {"type": "integer"}},
    },
    tier=1, data_class="third_party",
    executor=_exec_read_calendar,
))


def _exec_read_weather(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.weather import get_weather, get_current
    # Get household lat/lng; fall back to IP-based geo stub if not set
    lat, lng = _household_latlng(ctx)
    if lat is None or lng is None:
        raise ToolUnavailable("read_weather: household address/coordinates not set — add address in Settings")
    days = int(args.get("days", 3))
    result = get_weather(lat, lng, days=days)
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "openweather", cost_usd=0.0)
    return result

register(Tool(
    name="read_weather",
    description="Read weather forecast for the household location.",
    input_schema={
        "type": "object",
        "properties": {"days": {"type": "integer"}, "when": {"type": "string"}},
    },
    tier=1, data_class="third_party",
    executor=_exec_read_weather,
    cost_usd=0.001,
))


def _exec_read_package_status(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.packages import get_tracking
    tracking_id = args["tracking_id"]
    carrier = args.get("carrier")
    result = get_tracking(tracking_id, carrier=carrier)
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "aftership", cost_usd=0.005)
    return result

register(Tool(
    name="read_package_status",
    description="Look up status for a tracking number.",
    input_schema={
        "type": "object",
        "properties": {"tracking_id": {"type": "string"}},
        "required": ["tracking_id"],
    },
    tier=1, data_class="third_party",
    executor=_exec_read_package_status,
    cost_usd=0.005,
))


def _exec_geocode(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.maps import geocode
    result = geocode(args["address"])
    # Auto-update household coordinates if they're not set yet
    if ctx.household_id and result.get("lat") is not None:
        conn = db.get_connection()
        row = conn.execute(
            "SELECT lat FROM households WHERE id=?", (ctx.household_id,)
        ).fetchone()
        if row and row["lat"] is None:
            with conn:
                conn.execute(
                    "UPDATE households SET lat=?, lng=? WHERE id=?",
                    (result["lat"], result["lng"], ctx.household_id),
                )
        conn.close()
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "google_maps", cost_usd=0.005)
    return result

register(Tool(
    name="geocode",
    description="Convert an address string into lat/lng.",
    input_schema={
        "type": "object",
        "properties": {"address": {"type": "string"}},
        "required": ["address"],
    },
    tier=1, data_class="third_party",
    executor=_exec_geocode,
    cost_usd=0.005,
))


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2 — internal writes (auto by default; reversible)
# ─────────────────────────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def _slugify(s: str) -> str:
    return _SLUG_RE.sub("_", s.lower().strip()).strip("_") or "list"


def _exec_add_to_list(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        raise ToolError("no household — call get_or_create_household first")
    list_slug = args["list_slug"]
    item_label = args["item"]
    qty = args.get("qty")
    list_row = db.get_or_create_list(ctx.household_id, _slugify(list_slug),
                                     label=list_slug.replace("_", " ").title())
    iid = db.add_list_item(list_row["id"], item_label, qty=qty, source="agent")
    return {"item_id": iid, "list_id": list_row["id"], "list_slug": list_row["slug"]}


register(Tool(
    name="add_to_list",
    description=(
        "Append an item to a household list, creating the list if needed. "
        "Common slugs: grocery, hardware, pharmacy, weekly_errands."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "list_slug": {"type": "string"},
            "item":      {"type": "string"},
            "qty":       {"type": "string"},
        },
        "required": ["list_slug", "item"],
    },
    tier=2, data_class="internal",
    executor=_exec_add_to_list,
))


def _exec_update_list_item(ctx: ToolContext, args: dict) -> dict:
    item_id = args["item_id"]
    status = args["status"]
    ok = db.update_list_item_status(item_id, status)
    if not ok:
        raise ToolError(f"item {item_id} not found")
    return {"updated": True, "status": status}


register(Tool(
    name="update_list_item",
    description="Mark a list item as open|done|dropped.",
    input_schema={
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "status":  {"type": "string", "enum": ["open", "done", "dropped"]},
        },
        "required": ["item_id", "status"],
    },
    tier=2, data_class="internal",
    executor=_exec_update_list_item,
))


def _exec_update_inventory(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        raise ToolError("no household")
    label = args["item_label"]
    action = args["action"]

    # Find existing or create on the fly.
    rows = db.list_inventory(ctx.household_id)
    match = next((r for r in rows if r["label"].lower() == label.lower()), None)
    if not match:
        item_id = db.upsert_inventory_item(ctx.household_id, label, source="agent")
    else:
        item_id = match["id"]

    if action == "used":
        db.mark_inventory_used(item_id)
    elif action == "restocked":
        db.mark_inventory_used(item_id)  # restock resets the lifetime clock
    elif action == "lost":
        # Same effect as used, plus a log entry — we keep schema simple by
        # reusing mark_inventory_used and letting the action_log carry the
        # qualitative distinction.
        db.mark_inventory_used(item_id)
    return {"item_id": item_id, "action": action}


register(Tool(
    name="update_inventory",
    description=(
        "Mark an inventory item as restocked|used|lost. Creates the item if "
        "missing. The decay scan will recalculate low-stock from this."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "item_label": {"type": "string"},
            "action":     {"type": "string", "enum": ["restocked", "used", "lost"]},
        },
        "required": ["item_label", "action"],
    },
    tier=2, data_class="internal",
    executor=_exec_update_inventory,
))


def _exec_schedule_reminder(ctx: ToolContext, args: dict) -> dict:
    """
    Reminders are stored as home_events with kind='custom' for now —
    the existing scheduler + future push-notification path picks them up.
    """
    if not ctx.household_id:
        raise ToolError("no household")
    title = args["text"]
    when_at = args["when_at"]
    eid = db.upsert_home_event(
        ctx.household_id, title=title, when_at=when_at, kind="custom",
        source="agent",
    )
    return {"event_id": eid, "when_at": when_at}


register(Tool(
    name="schedule_reminder",
    description="Schedule a reminder for the user (internal — not pushed externally).",
    input_schema={
        "type": "object",
        "properties": {
            "text":    {"type": "string"},
            "when_at": {"type": "string", "description": "ISO-8601 timestamp"},
        },
        "required": ["text", "when_at"],
    },
    tier=2, data_class="internal",
    executor=_exec_schedule_reminder,
))


def _exec_log_observation(ctx: ToolContext, args: dict) -> dict:
    text = args["text"]
    domain = args.get("domain")
    db.log_action(ctx.user_id, "agent_observation", text,
                  payload={"domain": domain, "session_id": ctx.session_id})
    return {"logged": True}


register(Tool(
    name="log_observation",
    description=(
        "Log a free-form observation that doesn't fit elsewhere. Use sparingly — "
        "prefer update_context for durable facts."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "text":   {"type": "string"},
            "domain": {"type": "string"},
        },
        "required": ["text"],
    },
    tier=2, data_class="internal",
    executor=_exec_log_observation,
))


def _exec_update_context(ctx: ToolContext, args: dict) -> dict:
    domain = args["domain"]
    key = args["key"]
    value = args["value"]
    db.upsert_context(ctx.user_id, domain, key, value, source="inferred", confidence=0.7)
    return {"upserted": True}


register(Tool(
    name="update_context",
    description=(
        "Write to the life_context store. Source is recorded as 'inferred' "
        "(agent-generated). Use for durable facts the user has implicitly "
        "stated. Do NOT use for transient state — use update_inventory or "
        "schedule_reminder instead."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "key":    {"type": "string"},
            "value":  {"type": "string"},
        },
        "required": ["domain", "key", "value"],
    },
    tier=2, data_class="internal",
    executor=_exec_update_context,
))


def _exec_upsert_home_event(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        raise ToolError("no household")
    eid = db.upsert_home_event(
        ctx.household_id,
        title=args["title"],
        when_at=args["when_at"],
        kind=args.get("kind", "custom"),
        vendor_id=args.get("vendor_id"),
        member_id=args.get("member_id"),
        source="agent",
    )
    return {"event_id": eid}


register(Tool(
    name="upsert_home_event",
    description="Create a household event (service visit, school pickup, chore, etc.).",
    input_schema={
        "type": "object",
        "properties": {
            "title":     {"type": "string"},
            "when_at":   {"type": "string"},
            "kind":      {"type": "string",
                           "enum": ["service", "delivery", "school", "pickup",
                                    "chore", "custom"]},
            "vendor_id": {"type": "string"},
            "member_id": {"type": "string"},
        },
        "required": ["title", "when_at"],
    },
    tier=2, data_class="internal",
    executor=_exec_upsert_home_event,
))


def _exec_record_world_fact(ctx: ToolContext, args: dict) -> dict:
    if not ctx.household_id:
        raise ToolError("no household")
    src_kind = args["src_kind"]
    src_label = args["src_label"]
    dst_kind = args["dst_kind"]
    dst_label = args["dst_label"]
    predicate = args["predicate"]
    confidence = float(args.get("confidence", 1.0))
    src_id = db.upsert_home_entity(ctx.household_id, src_kind, src_label)
    dst_id = db.upsert_home_entity(ctx.household_id, dst_kind, dst_label)
    rid = db.upsert_home_relation(ctx.household_id, src_id, predicate, dst_id, confidence)
    return {"relation_id": rid, "src_id": src_id, "dst_id": dst_id}


register(Tool(
    name="record_world_fact",
    description=(
        "Record a relationship in the household world model — e.g. "
        "(fridge, located_in, kitchen). Entities are upserted. Use this to "
        "grow the model as you learn the home's shape."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "src_kind":   {"type": "string"},
            "src_label":  {"type": "string"},
            "predicate":  {"type": "string"},
            "dst_kind":   {"type": "string"},
            "dst_label":  {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["src_kind", "src_label", "predicate", "dst_kind", "dst_label"],
    },
    tier=2, data_class="internal",
    executor=_exec_record_world_fact,
))


def _exec_open_campaign(ctx: ToolContext, args: dict) -> dict:
    cid = db.create_campaign(
        ctx.user_id, ctx.household_id,
        intent=args["intent"],
        watcher=args.get("watcher", {}),
        summary=args.get("summary"),
        expires_in_days=int(args.get("expires_in_days", 60)),
        parent_session_id=ctx.session_id,
    )
    return {"campaign_id": cid}


register(Tool(
    name="open_campaign",
    description=(
        "Open a standing intent. Use for multi-day jobs the agent should "
        "resume on future triggers (HVAC scheduling, package tracking, "
        "guest visit prep). The watcher is a JSON object whose keys match "
        "future trigger payloads (e.g. {trigger_kind: 'webhook:delivery'})."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "intent":          {"type": "string"},
            "summary":         {"type": "string"},
            "watcher":         {"type": "object"},
            "expires_in_days": {"type": "integer"},
        },
        "required": ["intent"],
    },
    tier=2, data_class="internal",
    executor=_exec_open_campaign,
))


def _exec_close_campaign(ctx: ToolContext, args: dict) -> dict:
    cid = args["campaign_id"]
    status = args.get("status", "complete")
    ok = db.close_campaign(cid, status=status)
    if not ok:
        raise ToolError(f"campaign {cid} not closeable (already closed or unknown)")
    return {"closed": True, "status": status}


register(Tool(
    name="close_campaign",
    description="Close a standing intent. Status: complete|cancelled|blocked.",
    input_schema={
        "type": "object",
        "properties": {
            "campaign_id": {"type": "string"},
            "status":      {"type": "string",
                             "enum": ["complete", "cancelled", "blocked"]},
        },
        "required": ["campaign_id"],
    },
    tier=2, data_class="internal",
    executor=_exec_close_campaign,
))


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3 — external/visible (DRAFT by default)
# ─────────────────────────────────────────────────────────────────────────────
#
# These executors are called only when approval == "auto" — which for Tier 3
# requires either explicit user policy override or earned promotion. Until
# integrations land, they raise ToolUnavailable. The agent loop drafts them
# correctly regardless: drafting is a function of approval policy, not
# executor success.

def _exec_send_sms(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.sms import send_sms as _send
    recipient_id = args["recipient_id"]
    body = args["body"]
    # Resolve phone from member or vendor
    phone = _resolve_phone(recipient_id, ctx)
    if not phone:
        raise ToolError(f"no phone number for recipient {recipient_id!r} — add one in household settings")
    result = _send(phone, body)
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "twilio", cost_usd=0.0079)
    return {**result, "to": phone}

register(Tool(
    name="send_sms",
    description=(
        "Send an SMS to a household member or vendor. By default this is "
        "drafted for user confirmation; auto-send only fires after the tool "
        "has been promoted via the trust system."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "recipient_id":   {"type": "string",
                                "description": "member_id or vendor_id"},
            "body":           {"type": "string"},
        },
        "required": ["recipient_id", "body"],
    },
    tier=3, data_class="third_party",
    executor=_exec_send_sms,
    cost_usd=0.01,
))


def _exec_send_email(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.email_send import send_email as _send
    recipient_id = args["recipient_id"]
    email_addr = _resolve_email(recipient_id, ctx)
    if not email_addr:
        raise ToolError(f"no email address for recipient {recipient_id!r} — add one in household settings")
    result = _send(email_addr, args["subject"], args["body"])
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "resend", cost_usd=0.001)
    return result

register(Tool(
    name="send_email",
    description="Send an email to a household member or vendor (drafted by default).",
    input_schema={
        "type": "object",
        "properties": {
            "recipient_id": {"type": "string"},
            "subject":      {"type": "string"},
            "body":         {"type": "string"},
        },
        "required": ["recipient_id", "subject", "body"],
    },
    tier=3, data_class="third_party",
    executor=_exec_send_email,
    cost_usd=0.001,
))


def _exec_add_to_calendar(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.calendar import CalendarClient
    client = CalendarClient(ctx.user_id)
    result = client.create_event(
        title=args["title"],
        start_iso=args["when_at"],
        duration_minutes=int(args.get("duration_minutes", 60)),
        attendees=args.get("attendees") or [],
    )
    if ctx.session_id:
        db.record_integration_cost(ctx.user_id, "google_calendar", cost_usd=0.001)
    return result

register(Tool(
    name="add_to_calendar",
    description="Create a calendar event on the user's primary calendar (drafted by default).",
    input_schema={
        "type": "object",
        "properties": {
            "title":      {"type": "string"},
            "when_at":    {"type": "string"},
            "duration_minutes": {"type": "integer"},
            "attendees":  {"type": "array"},
        },
        "required": ["title", "when_at"],
    },
    tier=3, data_class="third_party",
    executor=_exec_add_to_calendar,
))


def _exec_request_service(ctx: ToolContext, args: dict) -> dict:
    """
    Composite tool — always runs at draft tier. The approval engine will
    always create a draft for this; this executor fires only on confirm.
    On confirm, it attempts to send the message and create a calendar hold.
    """
    vendor_id = args["vendor_id"]
    summary   = args["summary"]
    when      = args.get("when")

    vendor = db.get_vendor(vendor_id)
    if not vendor:
        raise ToolError(f"vendor {vendor_id!r} not found")

    results: dict = {"vendor": vendor["name"]}

    # Send message via best available channel (phone → SMS, else email)
    phone = vendor["phone"]
    email = vendor["email"]
    if phone:
        from vello.agent.integrations.sms import send_sms as _send
        try:
            results["sms"] = _send(phone, f"Hi, {summary}{' on ' + when if when else ''}. Please confirm.")
        except ToolUnavailable:
            results["sms"] = {"unavailable": True}
    elif email:
        from vello.agent.integrations.email_send import send_email as _send
        try:
            results["email"] = _send(email, f"Service request: {summary}", summary + (f"\n\nPreferred date: {when}" if when else ""))
        except ToolUnavailable:
            results["email"] = {"unavailable": True}

    # Tentative calendar hold
    if when:
        try:
            from vello.agent.integrations.calendar import CalendarClient
            cal_result = CalendarClient(ctx.user_id).create_event(
                title=f"Service: {vendor['name']} — {summary}",
                start_iso=when,
                duration_minutes=120,
                description=summary,
            )
            results["calendar"] = cal_result
        except ToolUnavailable:
            results["calendar"] = {"unavailable": True}

    return results

register(Tool(
    name="request_service",
    description=(
        "Compose a service request to a vendor. This is a single draft that "
        "expands into both a message to the vendor AND a tentative calendar "
        "hold when the user confirms. Use for HVAC, plumber, cleaner, etc."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "vendor_id": {"type": "string"},
            "summary":   {"type": "string"},
            "when":      {"type": "string"},
        },
        "required": ["vendor_id", "summary"],
    },
    tier=3, data_class="third_party",
    executor=_exec_request_service,
))


def _exec_push_to_kortex(ctx: ToolContext, args: dict) -> dict:
    raise ToolUnavailable(
        "push_to_kortex: requires Kortex /vello/observations endpoint (cross-repo)"
    )

register(Tool(
    name="push_to_kortex",
    description=(
        "Push a durable observation back to Kortex (the user's persistent "
        "memory engine). Use for facts that should outlive Vello's "
        "operational state (dietary patterns, vendor preferences, key "
        "addresses). Only fires when the user has connected Kortex."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "domain":     {"type": "string"},
            "key":        {"type": "string"},
            "value":      {"type": "string"},
            "confidence": {"type": "number"},
            "evidence":   {"type": "string"},
        },
        "required": ["domain", "key", "value"],
    },
    tier=3, data_class="kortex",
    executor=_exec_push_to_kortex,
))


# ─────────────────────────────────────────────────────────────────────────────
# TIER 4 — irreversible / cost (always confirm)
# ─────────────────────────────────────────────────────────────────────────────

def _exec_cancel_event(ctx: ToolContext, args: dict) -> dict:
    from vello.agent.integrations.calendar import CalendarClient
    CalendarClient(ctx.user_id).delete_event(args["event_id"])
    if args.get("reason"):
        db.log_action(ctx.user_id, "event_cancelled",
                      f"cancelled event {args['event_id']}: {args['reason']}",
                      payload={"event_id": args["event_id"], "reason": args["reason"]})
    return {"cancelled": True, "event_id": args["event_id"]}

register(Tool(
    name="cancel_event",
    description="Cancel a previously-scheduled calendar event. Always confirmed by user.",
    input_schema={
        "type": "object",
        "properties": {
            "event_id": {"type": "string"},
            "reason":   {"type": "string"},
        },
        "required": ["event_id"],
    },
    tier=4, data_class="third_party",
    executor=_exec_cancel_event,
))


def _exec_remove_household_member(ctx: ToolContext, args: dict) -> dict:
    raise ToolUnavailable(
        "remove_household_member: tier-4 — always drafted for user confirmation"
    )

register(Tool(
    name="remove_household_member",
    description="Remove a member from the household. Tier 4 — always confirmed.",
    input_schema={
        "type": "object",
        "properties": {
            "member_id": {"type": "string"},
            "reason":    {"type": "string"},
        },
        "required": ["member_id"],
    },
    tier=4, data_class="internal",
    executor=_exec_remove_household_member,
))


def _exec_external_write(ctx: ToolContext, args: dict) -> dict:
    raise ToolUnavailable(
        "external_write: tier-4 escape hatch — always drafted for user review"
    )

register(Tool(
    name="external_write",
    description=(
        "Generic escape hatch for writes that don't fit other tools. Always "
        "drafted; the user reviews payload before any external call."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "channel":  {"type": "string"},
            "payload":  {"type": "object"},
        },
        "required": ["channel", "payload"],
    },
    tier=4, data_class="third_party",
    executor=_exec_external_write,
))


# ── Summary helper ───────────────────────────────────────────────────────────

def _household_latlng(ctx: ToolContext) -> tuple[float | None, float | None]:
    if not ctx.household_id:
        return None, None
    conn = db.get_connection()
    row = conn.execute(
        "SELECT lat, lng FROM households WHERE id=?", (ctx.household_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None, None
    return (row["lat"], row["lng"])


def _resolve_phone(recipient_id: str, ctx: ToolContext) -> str | None:
    """Look up phone from household_members or vendors by id."""
    member = db.get_household_member(recipient_id)
    if member:
        try:
            channels = json.loads(member["channels_json"] or "{}")
            return channels.get("sms") or channels.get("phone")
        except (ValueError, TypeError):
            return None
    vendor = db.get_vendor(recipient_id)
    if vendor:
        return vendor["phone"]
    return None


def _resolve_email(recipient_id: str, ctx: ToolContext) -> str | None:
    """Look up email from household_members or vendors by id."""
    member = db.get_household_member(recipient_id)
    if member:
        try:
            channels = json.loads(member["channels_json"] or "{}")
            return channels.get("email")
        except (ValueError, TypeError):
            return None
    vendor = db.get_vendor(recipient_id)
    if vendor:
        return vendor["email"]
    return None


def summarize_for_draft(tool_name: str, args: dict) -> str:
    """
    Cheap deterministic summary used as the visible text on a draft card.
    Avoids an LLM round-trip — the planner already wrote `summary`/`body`
    fields where they exist.
    """
    if tool_name == "send_sms":
        return f"SMS to {args.get('recipient_id', '?')}: {args.get('body', '')[:120]}"
    if tool_name == "send_email":
        return f"Email to {args.get('recipient_id', '?')} — {args.get('subject', '')}"
    if tool_name == "add_to_calendar":
        return f"Calendar: {args.get('title', '')} @ {args.get('when_at', '')}"
    if tool_name == "request_service":
        when = args.get("when") or "(no time set)"
        return f"Service request to vendor {args.get('vendor_id', '?')}: {args.get('summary', '')} — {when}"
    if tool_name == "push_to_kortex":
        return (
            f"Push to Kortex: {args.get('domain', '?')}/{args.get('key', '?')} = "
            f"{str(args.get('value', ''))[:80]}"
        )
    if tool_name == "cancel_event":
        return f"Cancel event {args.get('event_id', '?')}: {args.get('reason', '')}"
    if tool_name == "remove_household_member":
        return f"Remove household member {args.get('member_id', '?')}: {args.get('reason', '')}"
    if tool_name == "external_write":
        return f"External write via {args.get('channel', '?')}"
    return f"{tool_name}({json.dumps(args, sort_keys=True)[:120]})"
