"""Action drafts inbox — confirm, edit, dismiss."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db
from vello.agent.tools import ToolContext, ToolError, ToolUnavailable, dispatch

router = APIRouter()


class EditBody(BaseModel):
    args: dict


@router.get("/")
def list_drafts(status: str = "pending", user=Depends(get_current_user)):
    rows = db.list_drafts(user["id"], status=status)
    return [dict(r) for r in rows]


@router.post("/{draft_id}/confirm")
def confirm_draft(draft_id: str, user=Depends(get_current_user)):
    draft = db.get_draft(user["id"], draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="not_found")
    if draft["status"] != "pending":
        raise HTTPException(status_code=409, detail="already_resolved")

    import json
    args = json.loads(draft["edited_args_json"] or draft["tool_args_json"] or "{}")
    hh = db.get_or_create_household(user["id"])
    ctx = ToolContext(user_id=user["id"], household_id=hh["id"], session_id=draft["session_id"])

    try:
        result = dispatch(draft["tool_name"], args, ctx)
        db.update_draft_status(draft_id, "executed")
        db.bump_tool_stat(user["id"], draft["tool_name"], "confirmed")
        db.log_action(user["id"], "draft_confirmed",
                       f"confirmed draft for {draft['tool_name']}",
                       payload={"draft_id": draft_id, "result": result})
        return {"ok": True, "result": result}
    except ToolUnavailable as exc:
        db.update_draft_status(draft_id, "failed", error_text=str(exc))
        raise HTTPException(status_code=503, detail=str(exc))
    except ToolError as exc:
        db.update_draft_status(draft_id, "failed", error_text=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{draft_id}/dismiss", status_code=204)
def dismiss_draft(draft_id: str, user=Depends(get_current_user)):
    draft = db.get_draft(user["id"], draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="not_found")
    db.update_draft_status(draft_id, "dismissed")
    db.bump_tool_stat(user["id"], draft["tool_name"], "dismissed")
    db.log_action(user["id"], "draft_dismissed",
                   f"dismissed draft for {draft['tool_name']}",
                   payload={"draft_id": draft_id})


@router.patch("/{draft_id}/edit")
def edit_draft(draft_id: str, body: EditBody, user=Depends(get_current_user)):
    draft = db.get_draft(user["id"], draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="not_found")
    if draft["status"] != "pending":
        raise HTTPException(status_code=409, detail="already_resolved")
    db.update_draft_args(draft_id, body.args)
    db.bump_tool_stat(user["id"], draft["tool_name"], "edited")
    return {"ok": True}
