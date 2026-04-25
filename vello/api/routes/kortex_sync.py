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
from vello.database import (
    set_kortex_token, upsert_context, get_user_by_id,
    has_active_trigger, get_active_watch, create_signal_trigger, create_signal_watch,
    create_inference,
)
from vello.signals import scan_text, get_transitions_for

router = APIRouter()


def _fire_signals(user_id: str, text: str) -> int:
    """
    Scan text for intent signals, fire new triggers respecting dedup + watches,
    and activate downstream watches for any signals that fire.
    Returns count of newly-created triggers.
    """
    if not text.strip():
        return 0

    fired = 0
    for match in scan_text(text):
        sid = match["signal_id"]
        watch = get_active_watch(user_id, sid)

        # Decide whether to fire:
        # - No active trigger → always fire
        # - Active watch with factor=0 → bypass dedup, always fire
        # - Active watch with factor>0 → handled by has_active_trigger (dedup still applies)
        # - No watch, active trigger → skip (normal anti-fatigue)
        if has_active_trigger(user_id, sid):
            if watch is None or watch["factor"] > 0:
                continue  # blocked by dedup

        create_signal_trigger(
            user_id=user_id,
            signal_id=sid,
            label=match["label"],
            priority=match["priority"],
            action_type=match["action_type"],
            trigger_message=match["trigger_message"],
            source_text=text[:500] if len(text) > 500 else text,
            decay_hours=match["decay_hours"],
        )
        fired += 1

        # Activate downstream watches for related signals
        for transition in get_transitions_for(sid):
            create_signal_watch(
                user_id=user_id,
                watched_signal_id=transition["signal_id"],
                triggered_by=sid,
                factor=transition["factor"],
                watch_hours=transition["watch_hours"],
            )

    return fired


class TokenBody(BaseModel):
    token: str


@router.post("/connect")
async def connect_kortex(body: TokenBody, user=Depends(get_current_user)):
    """Validate the Kortex token and store it."""
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
    """
    Pull Kortex profile and populate life_context.
    Also:
    - Scans imported text for intent signals (with chaining)
    - Imports pending contradictions as Vello inferences for dashboard review
    """
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

    # Import life context
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

    # Also scan high-confidence fact values
    for fact in data.get("facts", []):
        text_parts.append(str(fact.get("value", "")))

    # Fire signals with chaining
    combined_text = " ".join(text_parts)
    signals_fired = _fire_signals(user["id"], combined_text)

    # Import contradictions as Vello inferences for dashboard review
    contradictions_imported = 0
    for c in data.get("contradictions", []):
        create_inference(
            user["id"],
            inference_type="contradiction",
            description=(
                f"Contradiction in {c['domain']}.{c['path']}: "
                f"previously "{c['old_value']}", now "{c['new_value']}". "
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
