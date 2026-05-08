"""World model — household entities + relations."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db

router = APIRouter()

ENTITY_KINDS = {"room", "object", "member", "vendor", "recurring_event"}


class EntityBody(BaseModel):
    kind: str
    label: str
    metadata: Optional[dict] = None


class RelationBody(BaseModel):
    src_entity_id: str
    predicate: str
    dst_entity_id: str
    confidence: float = 1.0


@router.get("/entities")
def list_entities(kind: Optional[str] = None, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rows = db.list_home_entities(hh["id"], kind=kind)
    return [dict(r) for r in rows]


@router.post("/entities", status_code=201)
def create_entity(body: EntityBody, user=Depends(get_current_user)):
    if body.kind not in ENTITY_KINDS:
        raise HTTPException(status_code=422, detail="invalid_kind")
    hh = db.get_or_create_household(user["id"])
    eid = db.upsert_home_entity(hh["id"], body.kind, body.label, metadata=body.metadata)
    return {"id": eid}


@router.get("/relations")
def list_relations(predicate: Optional[str] = None, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rows = db.query_home_relations(hh["id"], predicate=predicate)
    return [dict(r) for r in rows]


@router.post("/relations", status_code=201)
def create_relation(body: RelationBody, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rid = db.upsert_home_relation(
        hh["id"], body.src_entity_id, body.predicate,
        body.dst_entity_id, body.confidence,
    )
    return {"id": rid}
