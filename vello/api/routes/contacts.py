from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello.database import create_contact, get_contacts, delete_contact

router = APIRouter()

NOTIFY_MODES = {"confirm", "auto", "draft"}


class ContactBody(BaseModel):
    label: str
    name: str
    phone: Optional[str] = None
    notify_mode: str = "confirm"


@router.get("/")
def list_contacts(user=Depends(get_current_user)):
    rows = get_contacts(user["id"])
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def add_contact(body: ContactBody, user=Depends(get_current_user)):
    if body.notify_mode not in NOTIFY_MODES:
        raise HTTPException(status_code=422, detail="invalid_notify_mode")
    cid = create_contact(user["id"], body.label, body.name, body.phone, body.notify_mode)
    return {"id": cid}


@router.delete("/{contact_id}", status_code=204)
def remove_contact(contact_id: str, user=Depends(get_current_user)):
    if not delete_contact(user["id"], contact_id):
        raise HTTPException(status_code=404, detail="not_found")
