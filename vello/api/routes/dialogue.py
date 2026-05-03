from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from vello.api.deps import get_current_user
from vello.config import MAX_DIALOGUE_MESSAGE_CHARS
from vello.database import (
    get_dialogue_history,
    record_rate_limit_attempt,
    count_recent_rate_limit_attempts,
)
from vello.dialogue import chat

router = APIRouter()


class MessageBody(BaseModel):
    # Bounded — every message hits the LLM, so unbounded input is a budget-drain vector.
    message: str = Field(..., max_length=MAX_DIALOGUE_MESSAGE_CHARS)


@router.get("/history")
def history(user=Depends(get_current_user)):
    rows = get_dialogue_history(user["id"], limit=50)
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in rows]


# Per-user dialogue rate limit — protects against runaway loops draining LLM budget.
_DIALOGUE_PER_HOUR = 60


@router.post("/")
def send_message(body: MessageBody, user=Depends(get_current_user)):
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="empty_message")

    if count_recent_rate_limit_attempts("dialogue", user["id"], window_seconds=3600) >= _DIALOGUE_PER_HOUR:
        raise HTTPException(status_code=429, detail="too_many_messages",
                            headers={"Retry-After": "3600"})
    record_rate_limit_attempt("dialogue", user["id"])

    history = get_dialogue_history(user["id"], limit=1)
    is_first = len(history) == 0

    result = chat(user["id"], body.message.strip(), is_first_message=is_first)
    return result


@router.post("/start")
def start_onboarding(user=Depends(get_current_user)):
    """Trigger the opening Vello message for a fresh user."""
    history = get_dialogue_history(user["id"], limit=1)
    if history:
        return {"message": None, "already_started": True}

    result = chat(user["id"], "__init__", is_first_message=True)
    return result
