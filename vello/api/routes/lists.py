"""Household lists and list items."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db

router = APIRouter()

LIST_KINDS = {"grocery", "hardware", "pharmacy", "weekly_errands", "custom"}
ITEM_STATUSES = {"open", "done", "dropped"}


class ListBody(BaseModel):
    slug: str
    label: Optional[str] = None
    kind: str = "custom"


class ItemBody(BaseModel):
    label: str
    qty: Optional[str] = None
    source: str = "user"


class ItemStatusBody(BaseModel):
    status: str


@router.get("/")
def get_lists(user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    lists = db.list_lists(hh["id"])
    out = []
    for l in lists:
        items = db.list_items_for_list(l["id"])
        out.append({**dict(l), "items": [dict(it) for it in items]})
    return out


@router.post("/", status_code=201)
def create_list(body: ListBody, user=Depends(get_current_user)):
    if body.kind not in LIST_KINDS:
        raise HTTPException(status_code=422, detail="invalid_kind")
    hh = db.get_or_create_household(user["id"])
    row = db.get_or_create_list(hh["id"], body.slug, label=body.label, kind=body.kind)
    return {"id": row["id"], "slug": row["slug"]}


@router.get("/{list_id}/items")
def get_items(list_id: str, status: Optional[str] = None, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    # Verify list belongs to this household
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM home_lists WHERE id=? AND household_id=?",
        (list_id, hh["id"]),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    items = db.list_items_for_list(list_id, status=status)
    return [dict(it) for it in items]


@router.post("/{list_id}/items", status_code=201)
def add_item(list_id: str, body: ItemBody, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM home_lists WHERE id=? AND household_id=?",
        (list_id, hh["id"]),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    iid = db.add_list_item(list_id, body.label, qty=body.qty, source=body.source)
    return {"id": iid}


@router.patch("/{list_id}/items/{item_id}")
def update_item(list_id: str, item_id: str, body: ItemStatusBody,
                user=Depends(get_current_user)):
    if body.status not in ITEM_STATUSES:
        raise HTTPException(status_code=422, detail="invalid_status")
    ok = db.update_list_item_status(item_id, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True}


@router.delete("/{list_id}/items/{item_id}", status_code=204)
def delete_item(list_id: str, item_id: str, user=Depends(get_current_user)):
    ok = db.update_list_item_status(item_id, "dropped")
    if not ok:
        raise HTTPException(status_code=404, detail="not_found")
