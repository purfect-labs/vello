from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

from vello.api.deps import get_current_user
from vello import database as db

router = APIRouter()

MEMBER_KINDS = {"person", "child", "pet"}
VENDOR_KINDS = {"handyman", "plumber", "electrician", "hvac", "sitter",
                "dogwalker", "cleaner", "vet", "custom"}


# ── Household ─────────────────────────────────────────────────────────────────

class HouseholdUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None


@router.get("/")
def get_household(user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    return dict(hh)


@router.patch("/")
def update_household(body: HouseholdUpdate, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    updates = body.model_dump(exclude_none=True)
    if updates:
        db.update_household(hh["id"], **updates)
    return dict(db.get_or_create_household(user["id"]))


# ── Members ───────────────────────────────────────────────────────────────────

class MemberBody(BaseModel):
    kind: str = "person"
    name: str
    relationship: Optional[str] = None
    dob: Optional[str] = None
    notes: Optional[str] = None
    channels: Optional[dict] = None
    consent: Optional[dict] = None


class MemberPreferenceBody(BaseModel):
    domain: str
    key: str
    value: str
    source: str = "manual"


@router.get("/members")
def list_members(user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rows = db.list_household_members(hh["id"])
    out = []
    for r in rows:
        m = dict(r)
        try:
            m["channels"] = json.loads(m.get("channels_json") or "{}")
            m["consent"]  = json.loads(m.get("consent_json")  or "{}")
        except (ValueError, TypeError):
            m["channels"] = {}
            m["consent"]  = {}
        out.append(m)
    return out


@router.post("/members", status_code=201)
def add_member(body: MemberBody, user=Depends(get_current_user)):
    if body.kind not in MEMBER_KINDS:
        raise HTTPException(status_code=422, detail="invalid_kind")
    hh = db.get_or_create_household(user["id"])
    mid = db.upsert_household_member(
        hh["id"], kind=body.kind, name=body.name,
        relationship=body.relationship,
        channels=body.channels, consent=body.consent,
        notes=body.notes,
    )
    return {"id": mid}


@router.delete("/members/{member_id}", status_code=204)
def remove_member(member_id: str, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    member = db.get_household_member(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="not_found")
    # verify ownership via household
    if member["household_id"] != hh["id"]:
        raise HTTPException(status_code=403, detail="forbidden")
    conn = db.get_connection()
    with conn:
        conn.execute("DELETE FROM household_members WHERE id=?", (member_id,))
    conn.close()


@router.post("/members/{member_id}/preferences", status_code=201)
def set_member_preference(member_id: str, body: MemberPreferenceBody,
                           user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    member = db.get_household_member(member_id)
    if not member or member["household_id"] != hh["id"]:
        raise HTTPException(status_code=404, detail="not_found")
    db.upsert_member_preference(member_id, body.domain, body.key, body.value, body.source)
    return {"ok": True}


@router.get("/members/{member_id}/preferences")
def get_member_preferences(member_id: str, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    member = db.get_household_member(member_id)
    if not member or member["household_id"] != hh["id"]:
        raise HTTPException(status_code=404, detail="not_found")
    rows = db.list_member_preferences(member_id)
    return [dict(r) for r in rows]


# ── Vendors ───────────────────────────────────────────────────────────────────

class VendorBody(BaseModel):
    name: str
    kind: str = "custom"
    phone: Optional[str] = None
    email: Optional[str] = None


@router.get("/vendors")
def list_vendors(kind: Optional[str] = None, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rows = db.list_vendors(hh["id"], kind=kind)
    return [dict(r) for r in rows]


@router.post("/vendors", status_code=201)
def add_vendor(body: VendorBody, user=Depends(get_current_user)):
    if body.kind not in VENDOR_KINDS:
        raise HTTPException(status_code=422, detail="invalid_kind")
    hh = db.get_or_create_household(user["id"])
    vid = db.create_vendor(hh["id"], body.name, kind=body.kind,
                            phone=body.phone, email=body.email)
    return {"id": vid}


@router.delete("/vendors/{vendor_id}", status_code=204)
def remove_vendor(vendor_id: str, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    row = db.get_vendor(vendor_id)
    if not row or row["household_id"] != hh["id"]:
        raise HTTPException(status_code=404, detail="not_found")
    conn = db.get_connection()
    with conn:
        conn.execute("DELETE FROM vendors WHERE id=?", (vendor_id,))
    conn.close()
