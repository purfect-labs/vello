from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vello.api.deps import get_current_user
from vello.database import (
    create_zone, get_zones, delete_zone,
    get_zone, record_location_event, get_recent_location_events,
)
from vello.signals import fire_signals

router = APIRouter()

ZONE_TYPES = {"home", "work", "gym", "custom"}
EVENT_TYPES = {"enter", "exit"}


class ZoneBody(BaseModel):
    label: str
    type: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_meters: int = 200


class LocationEventBody(BaseModel):
    zone_id:     str
    event_type:  str = Field(..., description="enter or exit")
    occurred_at: Optional[str] = None


@router.get("/")
def list_zones(user=Depends(get_current_user)):
    rows = get_zones(user["id"])
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def create(body: ZoneBody, user=Depends(get_current_user)):
    if body.type not in ZONE_TYPES:
        raise HTTPException(status_code=422, detail="invalid_type")
    zid = create_zone(user["id"], body.label, body.type, body.address,
                      body.lat, body.lng, body.radius_meters)
    return {"id": zid}


@router.delete("/{zone_id}", status_code=204)
def remove(zone_id: str, user=Depends(get_current_user)):
    if not delete_zone(user["id"], zone_id):
        raise HTTPException(status_code=404, detail="not_found")


# ── Location events (mobile geofence ingestion) ───────────────────────────────

@router.post("/event", status_code=201)
def record_event(body: LocationEventBody, user=Depends(get_current_user)):
    """
    Mobile clients post geofence enter/exit events here. We also feed the
    event into the temporal pattern engine (so first daily exit-from-home
    becomes a "wake_time"-style observation) and the signal scanner so
    exits to "work" zone after a long absence can hint at job changes etc.
    """
    if body.event_type not in EVENT_TYPES:
        raise HTTPException(status_code=422, detail="invalid_event_type")
    zone = get_zone(user["id"], body.zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="zone_not_found")

    eid = record_location_event(user["id"], body.zone_id, body.event_type, body.occurred_at)

    # Feed temporal observations: enter-home in evening, exit-home in morning, etc.
    try:
        from vello.temporal import log_observation
        from datetime import datetime, timezone
        when = datetime.fromisoformat(body.occurred_at) if body.occurred_at else datetime.now(timezone.utc)
        minutes = when.hour * 60 + when.minute
        # Pattern key like "exit_home" or "enter_work" — rich enough for the
        # bimodal split detector to cluster by behavior.
        pattern_key = f"{body.event_type}_{zone['type']}"
        label = f"{body.event_type.capitalize()} {zone['label']}"
        log_observation(user["id"], pattern_key, label, minutes)
    except Exception:
        pass  # observations are best-effort; never block the event

    # Lightweight signal text — gives the signal scanner a chance to chain.
    try:
        fire_signals(user["id"], f"{body.event_type} {zone['label']}")
    except Exception:
        pass

    return {"id": eid, "zone_id": body.zone_id, "event_type": body.event_type}


@router.get("/events")
def list_events(limit: int = 50, user=Depends(get_current_user)):
    """Recent enter/exit events for debugging / mobile sync."""
    if limit > 200:
        limit = 200
    rows = get_recent_location_events(user["id"], limit=limit)
    return [dict(r) for r in rows]
