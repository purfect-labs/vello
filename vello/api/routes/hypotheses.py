from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from vello.api.deps import get_current_user
from vello.hypotheses import attest as attest_h, list_active, list_open, retire as retire_h
from vello.database import get_connection

router = APIRouter()


@router.get("")
def list_hypotheses(status: str | None = None, user=Depends(get_current_user)):
    """active | open | all"""
    if status == "active":
        return list_active(user["id"])
    if status == "open":
        return list_open(user["id"])
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM hypotheses WHERE user_id=? ORDER BY status, confidence DESC",
        (user["id"],),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


class AttestBody(BaseModel):
    attested: bool


@router.post("/{hypothesis_id}/attest")
def attest(hypothesis_id: str, body: AttestBody, user=Depends(get_current_user)):
    if not attest_h(user["id"], hypothesis_id, body.attested):
        raise HTTPException(status_code=404, detail="hypothesis_not_found")
    return {"id": hypothesis_id, "user_attested": body.attested}


@router.delete("/{hypothesis_id}", status_code=204)
def reject(hypothesis_id: str, user=Depends(get_current_user)):
    if not retire_h(user["id"], hypothesis_id):
        raise HTTPException(status_code=404, detail="hypothesis_not_found")
