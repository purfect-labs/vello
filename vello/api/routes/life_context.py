from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello.database import get_context, upsert_context, delete_context_entry

router = APIRouter()

VALID_DOMAINS = {"schedule", "fitness", "work", "people", "home", "finance", "health", "preferences"}

DOMAIN_KEYS = {
    "schedule":    ["wake_time", "sleep_goal", "work_start", "work_end", "commute_type", "commute_minutes"],
    "fitness":     ["goal", "workout_days", "workout_time", "gym_location", "weekly_target", "activities"],
    "work":        ["location_type", "hybrid_days", "meeting_style"],
    "people":      ["partner_name", "partner_phone", "partner_notify_mode"],
    "home":        ["home_type", "occupant_count", "smart_home_platform"],
    "finance":     ["auto_spend_limit"],
    "health":      ["sleep_quality_goal", "dietary_notes"],
    "preferences": ["brief_style", "quiet_start", "quiet_end"],
}

DOMAIN_META = {
    "schedule":    {"label": "Your Day",        "description": "Wake time, sleep goal, work hours — helps Vello time reminders around your actual schedule."},
    "fitness":     {"label": "Movement",         "description": "Fitness goals and workout schedule — helps Vello protect workout time and reschedule intelligently."},
    "work":        {"label": "Work",             "description": "Where and how you work — helps Vello know when you're in focus mode vs. available."},
    "people":      {"label": "Your People",      "description": "Key contacts for coordination — Vello never reaches out without your approval."},
    "home":        {"label": "Home",             "description": "Your living situation and connected devices."},
    "finance":     {"label": "Spend Comfort",    "description": "Auto-spend limits — controls what Vello can handle vs. what needs your approval."},
    "health":      {"label": "Health Context",   "description": "Optional context that adds depth to fitness and routine recommendations."},
    "preferences": {"label": "Preferences",      "description": "How Vello communicates with you — brief style, quiet hours."},
}


class UpsertBody(BaseModel):
    domain: str
    key: str
    value: str


@router.get("/")
def get_all_context(user=Depends(get_current_user)):
    rows = get_context(user["id"])
    result = {}
    for domain, meta in DOMAIN_META.items():
        entries = {r["key"]: {"value": r["value"], "source": r["source"], "confidence": r["confidence"]}
                   for r in rows if r["domain"] == domain}
        result[domain] = {**meta, "keys": DOMAIN_KEYS.get(domain, []), "data": entries}
    return result


@router.get("/{domain}")
def get_domain(domain: str, user=Depends(get_current_user)):
    if domain not in VALID_DOMAINS:
        raise HTTPException(status_code=404, detail="unknown_domain")
    rows = get_context(user["id"], domain)
    return {r["key"]: {"value": r["value"], "source": r["source"]} for r in rows}


@router.put("/")
def upsert_entry(body: UpsertBody, user=Depends(get_current_user)):
    if body.domain not in VALID_DOMAINS:
        raise HTTPException(status_code=422, detail="unknown_domain")
    upsert_context(user["id"], body.domain, body.key, body.value, source="manual")
    return {"ok": True}


@router.delete("/{domain}/{key}")
def delete_entry(domain: str, key: str, user=Depends(get_current_user)):
    deleted = delete_context_entry(user["id"], domain, key)
    if not deleted:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True}
