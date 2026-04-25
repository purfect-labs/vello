from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello.database import create_zone, get_zones, delete_zone

router = APIRouter()

ZONE_TYPES = {"home", "work", "gym", "custom"}


class ZoneBody(BaseModel):
    label: str
    type: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_meters: int = 200


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
