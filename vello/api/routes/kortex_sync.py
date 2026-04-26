"""
Kortex ↔ Vello sync.
User supplies their Kortex personal token (ktx_...).
We pull the structured profile and map it into life_context entries,
scan imported text for intent signals (with chaining), and import
any pending contradictions as Vello inferences.
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from vello.api.deps import get_current_user
from vello.config import KORTEX_API_URL
from vello.database import set_kortex_token, upsert_context, get_user_by_id, create_inference
from vello.signals import fire_signals

router = APIRouter()


class TokenBody(BaseModel):
    token: str


@router.post("/connect")
async def connect_kortex(body: TokenBody, user=Depends(get_current_user)):
    if not body.token.startswith("ktx_"):
        raise HTTPException(status_code=422, detail="invalid_token_format")

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{KORTEX_API_URL}/user/token",
                headers={"Authorization": f"Bearer {body.token}"},
                timeout=10,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="kortex_unreachable")

    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="kortex_token_invalid")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="kortex_error")

    set_kortex_token(user["id"], body.token)
    return {"ok": True}


@router.post("/import")
async def import_from_kortex(user=Depends(get_current_user)):
    fresh_user = get_user_by_id(user["id"])
    token = fresh_user["kortex_token"] if fresh_user else None
    if not token:
        raise HTTPException(status_code=400, detail="kortex_not_connected")

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                f"{KORTEX_API_URL}/vello/export",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="kortex_unreachable")

    if r.status_code == 401:
        raise HTTPException(status_code=401, detail="kortex_token_invalid")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="kortex_error")

    data = r.json()
    imported = 0
    text_parts: list[str] = []

    for entry in data.get("life_context", []):
        upsert_context(
            user["id"],
            domain=entry["domain"],
            key=entry["key"],
            value=entry["value"],
            source="kortex",
            confidence=0.85,
        )
        imported += 1
        text_parts.append(entry["value"])

    for fact in data.get("facts", []):
        text_parts.append(str(fact.get("value", "")))

    signals_fired = fire_signals(user["id"], " ".join(text_parts))

    contradictions_imported = 0
    for c in data.get("contradictions", []):
        create_inference(
            user["id"],
            inference_type="contradiction",
            description=(
                f"Contradiction in {c['domain']}.{c['path']}: "
                f"previously '{c['old_value']}', now '{c['new_value']}'. "
                f"Which is current? ({c.get('rationale', 'no context')})"
            ),
            proposed={
                "domain":    c["domain"],
                "path":      c["path"],
                "old_value": c["old_value"],
                "new_value": c["new_value"],
                "kortex_id": c["id"],
            },
        )
        contradictions_imported += 1

    return {
        "imported":                imported,
        "signals_fired":           signals_fired,
        "contradictions_imported": contradictions_imported,
        "email":                   data.get("email"),
    }


@router.delete("/disconnect")
def disconnect_kortex(user=Depends(get_current_user)):
    set_kortex_token(user["id"], "")
    return {"ok": True}
