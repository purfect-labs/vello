"""
Webhook ingest — users wire Zapier/Make/n8n to POST text here.
Vello runs signal detection and context updates on the payload.
"""
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from vello.api.deps import get_current_user
from vello.database import (
    get_connection, has_active_trigger, get_active_watch,
    create_signal_trigger, create_signal_watch,
)
from vello.signals import scan_text, get_transitions_for

router = APIRouter()


def _get_user_by_token(token: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE webhook_token=?", (token,)).fetchone()
    conn.close()
    return row


def _fire_signals(user_id: str, text: str) -> int:
    fired = 0
    for match in scan_text(text):
        sid = match["signal_id"]
        watch = get_active_watch(user_id, sid)
        if has_active_trigger(user_id, sid):
            if watch is None or watch["factor"] > 0:
                continue
        create_signal_trigger(
            user_id=user_id,
            signal_id=sid,
            label=match["label"],
            priority=match["priority"],
            action_type=match["action_type"],
            trigger_message=match["trigger_message"],
            source_text=text[:500],
            decay_hours=match["decay_hours"],
        )
        fired += 1
        for transition in get_transitions_for(sid):
            create_signal_watch(
                user_id=user_id,
                watched_signal_id=transition["signal_id"],
                triggered_by=sid,
                factor=transition["factor"],
                watch_hours=transition["watch_hours"],
            )
    return fired


class IngestBody(BaseModel):
    text: str
    source: str = "webhook"


@router.post("/ingest")
def ingest(body: IngestBody, x_webhook_token: str = Header(...)):
    user = _get_user_by_token(x_webhook_token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_token")
    fired = _fire_signals(user["id"], body.text)
    return {"ok": True, "signals_fired": fired}


@router.get("/token")
def get_token(user=Depends(get_current_user)):
    return {"token": user["webhook_token"]}


@router.post("/token/regenerate")
def regenerate_token(user=Depends(get_current_user)):
    token = secrets.token_urlsafe(32)
    conn = get_connection()
    with conn:
        conn.execute("UPDATE users SET webhook_token=? WHERE id=?", (token, user["id"]))
    conn.close()
    return {"token": token}
