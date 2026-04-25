from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello.database import create_routine, get_routines, toggle_routine, delete_routine

router = APIRouter()

ROUTINE_TYPES = {"workout", "commute", "morning", "sleep", "medication", "custom"}


class RoutineBody(BaseModel):
    name: str
    type: str
    schedule: dict = {}


class ToggleBody(BaseModel):
    active: bool


@router.get("/")
def list_routines(user=Depends(get_current_user)):
    import json
    rows = get_routines(user["id"])
    result = []
    for r in rows:
        d = dict(r)
        d["schedule"] = json.loads(r["schedule_json"])
        del d["schedule_json"]
        result.append(d)
    return result


@router.post("/", status_code=201)
def create(body: RoutineBody, user=Depends(get_current_user)):
    if body.type not in ROUTINE_TYPES:
        raise HTTPException(status_code=422, detail="invalid_type")
    rid = create_routine(user["id"], body.name, body.type, body.schedule, source="manual")
    return {"id": rid}


@router.patch("/{routine_id}")
def toggle(routine_id: str, body: ToggleBody, user=Depends(get_current_user)):
    if not toggle_routine(user["id"], routine_id, body.active):
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True}


@router.delete("/{routine_id}", status_code=204)
def remove(routine_id: str, user=Depends(get_current_user)):
    if not delete_routine(user["id"], routine_id):
        raise HTTPException(status_code=404, detail="not_found")
