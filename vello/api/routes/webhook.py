"""
Webhook ingest — users wire Zapier/Make/n8n to POST text here.
Vello runs signal detection and lightweight context extraction on the payload.
"""
import json
import re
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from vello.api.deps import get_current_user
from vello.config import ANTHROPIC_API_KEY, LLM_API_KEY, DIALOGUE_MODEL
from vello.database import get_connection, upsert_context
from vello.llm import complete
from vello.signals import fire_signals

router = APIRouter()

_EXTRACT_SYSTEM = """\
Extract personal facts from the text below. Return ONLY valid JSON:
{"extracted": [{"domain": "...", "key": "...", "value": "...", "confidence": 0.0}]}
Domains: schedule, fitness, work, people, home, finance, health, preferences.
If nothing extractable, return {"extracted": []}. No markdown, no explanation.\
"""


def _get_user_by_token(token: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE webhook_token=?", (token,)).fetchone()
    conn.close()
    return row


def _extract_context(user_id: str, text: str) -> int:
    """Run LLM to extract life context from short webhook text."""
    try:
        raw = complete(
            _EXTRACT_SYSTEM,
            [{"role": "user", "content": text[:1500]}],
            model=DIALOGUE_MODEL,
            max_tokens=400,
        ).strip()
        if raw.startswith("```"):
            raw = re.sub(r"```[a-z]*\n?", "", raw).strip("`").strip()
        items = json.loads(raw).get("extracted", [])
    except Exception:
        return 0

    saved = 0
    for item in items:
        if item.get("domain") and item.get("key") and item.get("value"):
            upsert_context(
                user_id,
                domain=item["domain"],
                key=item["key"],
                value=str(item["value"]),
                source="webhook",
                confidence=float(item.get("confidence", 0.7)),
            )
            saved += 1
    return saved


class IngestBody(BaseModel):
    text: str = Field(..., max_length=10000)
    source: str = "webhook"


@router.post("/ingest")
def ingest(body: IngestBody, x_webhook_token: str = Header(...)):
    user = _get_user_by_token(x_webhook_token)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_token")

    signals_fired = fire_signals(user["id"], body.text)

    # For short texts (conversational length), also extract context
    context_saved = 0
    if len(body.text) <= 1500 and (ANTHROPIC_API_KEY or LLM_API_KEY):
        context_saved = _extract_context(user["id"], body.text)

    return {"ok": True, "signals_fired": signals_fired, "context_saved": context_saved}


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
