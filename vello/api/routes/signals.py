"""
Intent-signal trigger endpoints.

Signals are created automatically when text is scanned (on Kortex import,
dialogue, etc.). This router exposes them for dashboard display and resolution.
"""
from fastapi import APIRouter, Depends, HTTPException

from vello.api.deps import get_current_user
from vello.database import get_active_triggers, resolve_signal_trigger

router = APIRouter()


@router.get("/")
def list_triggers(user=Depends(get_current_user)):
    rows = get_active_triggers(user["id"])
    return [
        {
            "id":              r["id"],
            "signal_id":       r["signal_id"],
            "label":           r["label"],
            "priority":        r["priority"],
            "action_type":     r["action_type"],
            "trigger_message": r["trigger_message"],
            "created_at":      r["created_at"],
            "expires_at":      r["expires_at"],
        }
        for r in rows
    ]


@router.post("/{trigger_id}/confirm")
def confirm_trigger(trigger_id: str, user=Depends(get_current_user)):
    ok = resolve_signal_trigger(user["id"], trigger_id, "confirmed")
    if not ok:
        raise HTTPException(status_code=404, detail="trigger_not_found")
    return {"ok": True}


@router.post("/{trigger_id}/dismiss")
def dismiss_trigger(trigger_id: str, user=Depends(get_current_user)):
    ok = resolve_signal_trigger(user["id"], trigger_id, "dismissed")
    if not ok:
        raise HTTPException(status_code=404, detail="trigger_not_found")
    return {"ok": True}
