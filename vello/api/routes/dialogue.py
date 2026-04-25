from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from vello.api.deps import get_current_user
from vello.database import get_dialogue_history
from vello.dialogue import chat

router = APIRouter()


class MessageBody(BaseModel):
    message: str


@router.get("/history")
def history(user=Depends(get_current_user)):
    rows = get_dialogue_history(user["id"], limit=50)
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in rows]


@router.post("/")
def send_message(body: MessageBody, user=Depends(get_current_user)):
    if not body.message.strip():
        raise HTTPException(status_code=422, detail="empty_message")

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
