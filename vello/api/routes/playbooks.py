"""Playbook management — list, propose, accept, trigger."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db

router = APIRouter()


class PlaybookBody(BaseModel):
    slug: str
    title: str
    definition: dict
    confidence: float = 1.0


@router.get("/")
def list_playbooks(user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    rows = db.list_playbooks(household_id=hh["id"], enabled_only=False)
    return [dict(r) for r in rows]


@router.post("/", status_code=201)
def create_playbook(body: PlaybookBody, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    pid = db.upsert_playbook(
        household_id=hh["id"],
        slug=body.slug,
        title=body.title,
        definition=body.definition,
        source="manual",
        confidence=body.confidence,
    )
    return {"id": pid}


@router.post("/{playbook_id}/accept-learned")
def accept_learned(playbook_id: str, user=Depends(get_current_user)):
    """Confirm a learned-playbook proposal (source stays 'learned' but enabled=1)."""
    hh = db.get_or_create_household(user["id"])
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM playbooks WHERE id=? AND (household_id=? OR household_id IS NULL)",
        (playbook_id, hh["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="not_found")
    with conn:
        conn.execute("UPDATE playbooks SET enabled=1 WHERE id=?", (playbook_id,))
    conn.close()
    return {"ok": True}


@router.delete("/{playbook_id}", status_code=204)
def disable_playbook(playbook_id: str, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    conn = db.get_connection()
    row = conn.execute(
        "SELECT id FROM playbooks WHERE id=? AND (household_id=? OR household_id IS NULL)",
        (playbook_id, hh["id"]),
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="not_found")
    with conn:
        conn.execute("UPDATE playbooks SET enabled=0 WHERE id=?", (playbook_id,))
    conn.close()


@router.post("/{playbook_id}/run")
def run_playbook(playbook_id: str, user=Depends(get_current_user)):
    """Manually trigger an agent turn using this playbook as the intent."""
    hh = db.get_or_create_household(user["id"])
    conn = db.get_connection()
    row = conn.execute(
        "SELECT * FROM playbooks WHERE id=? AND (household_id=? OR household_id IS NULL)",
        (playbook_id, hh["id"]),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    from vello.agent.loop import run_agent_turn
    result = run_agent_turn(
        user_id=user["id"],
        trigger_kind="playbook_manual",
        trigger_payload={"playbook_id": playbook_id, "slug": row["slug"]},
    )
    return {
        "session_id":     result.session_id,
        "outcome":        result.outcome,
        "drafts_created": result.drafts_created,
    }
