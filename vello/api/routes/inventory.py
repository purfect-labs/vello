"""Household inventory management."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db

router = APIRouter()

ACTIONS = {"restocked", "used", "lost"}


class InventoryItemBody(BaseModel):
    label: str
    est_lifetime_days: Optional[int] = None
    low_threshold_days: Optional[int] = None
    location_entity_id: Optional[str] = None
    restock_url: Optional[str] = None
    source: str = "user"


class InventoryActionBody(BaseModel):
    action: str  # restocked | used | lost


@router.get("/")
def list_inventory(low_stock: bool = False, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rows = db.list_inventory(hh["id"], low_stock_only=low_stock)
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def add_item(body: InventoryItemBody, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    iid = db.upsert_inventory_item(
        hh["id"], body.label,
        est_lifetime_days=body.est_lifetime_days,
        low_threshold_days=body.low_threshold_days,
        location_entity_id=body.location_entity_id,
        source=body.source,
    )
    if body.restock_url:
        conn = db.get_connection()
        with conn:
            conn.execute("UPDATE inventory_items SET restock_url=? WHERE id=?",
                         (body.restock_url, iid))
        conn.close()
    return {"id": iid}


@router.post("/{item_id}/action")
def record_action(item_id: str, body: InventoryActionBody, user=Depends(get_current_user)):
    if body.action not in ACTIONS:
        raise HTTPException(status_code=422, detail="invalid_action")
    hh = db.get_or_create_household(user["id"])
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM inventory_items WHERE id=? AND household_id=?",
        (item_id, hh["id"]),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    db.mark_inventory_used(item_id)
    return {"ok": True}


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: str, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    conn = db.get_connection()
    row = conn.execute(
        "SELECT id FROM inventory_items WHERE id=? AND household_id=?",
        (item_id, hh["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="not_found")
    with conn:
        conn.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))
    conn.close()
