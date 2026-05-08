"""Agent trigger, session history, and campaign management."""
import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db
from vello.agent.loop import run_agent_turn
from vello.agent.approval import find_promotion_candidates

router = APIRouter()
log = logging.getLogger(__name__)


class TriggerBody(BaseModel):
    kind: str
    payload: Optional[dict] = None


class CampaignBody(BaseModel):
    intent: str
    summary: Optional[str] = None
    watcher: Optional[dict] = None
    expires_in_days: int = 60


@router.post("/trigger")
def trigger_agent(body: TriggerBody, background_tasks: BackgroundTasks,
                  user=Depends(get_current_user)):
    """
    Kick off an agent turn. For voice/user_request triggers the turn runs
    inline (short enough for a request timeout). For cron-alike trigger_kinds
    the turn runs in the background so the HTTP response returns immediately.
    """
    inline_kinds = {"user_request", "voice", "campaign_resume"}
    if body.kind in inline_kinds:
        result = run_agent_turn(
            user_id=user["id"],
            trigger_kind=body.kind,
            trigger_payload=body.payload or {},
        )
        return {
            "session_id":     result.session_id,
            "outcome":        result.outcome,
            "steps":          result.steps,
            "drafts_created": result.drafts_created,
            "need_info":      result.need_info,
            "defer_reason":   result.defer_reason,
            "finish_message": result.finish_message,
            "quality":        result.quality,
        }
    else:
        # Background — return immediately with a session_id placeholder.
        # The frontend polls /agent/sessions for updates.
        def _run():
            try:
                run_agent_turn(
                    user_id=user["id"],
                    trigger_kind=body.kind,
                    trigger_payload=body.payload or {},
                )
            except Exception as exc:
                log.error("background agent turn failed for user %s: %s", user["id"], exc)

        background_tasks.add_task(_run)
        return {"queued": True, "trigger_kind": body.kind}


@router.get("/sessions")
def list_sessions(limit: int = 30, user=Depends(get_current_user)):
    rows = db.list_agent_sessions(user["id"], limit=limit)
    return [dict(r) for r in rows]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, user=Depends(get_current_user)):
    row = db.get_agent_session(session_id)
    if not row or row["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="not_found")
    import json
    session = dict(row)
    try:
        session["plan"] = json.loads(session.get("plan_json") or "[]")
        session["quality"] = json.loads(session.get("quality_json") or "null")
    except (ValueError, TypeError):
        session["plan"] = []
        session["quality"] = None
    # Fetch tool calls for this session
    conn = db.get_connection()
    calls = conn.execute(
        "SELECT * FROM agent_tool_calls WHERE session_id=? ORDER BY idx",
        (session_id,),
    ).fetchall()
    conn.close()
    session["tool_calls"] = [dict(c) for c in calls]
    return session


@router.get("/campaigns")
def list_campaigns(user=Depends(get_current_user)):
    rows = db.list_open_campaigns(user["id"])
    return [dict(r) for r in rows]


@router.post("/campaigns", status_code=201)
def create_campaign(body: CampaignBody, user=Depends(get_current_user)):
    hh = db.get_or_create_household(user["id"])
    cid = db.create_campaign(
        user_id=user["id"],
        household_id=hh["id"],
        intent=body.intent,
        watcher=body.watcher or {},
        summary=body.summary,
        expires_in_days=body.expires_in_days,
    )
    return {"id": cid}


@router.post("/campaigns/{campaign_id}/close", status_code=204)
def close_campaign(campaign_id: str, user=Depends(get_current_user)):
    row = db.get_campaign(campaign_id)
    if not row or row["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="not_found")
    db.close_campaign(campaign_id, status="cancelled")


@router.get("/policy")
def get_policy(user=Depends(get_current_user)):
    return db.get_user_policy(user["id"])


@router.put("/policy")
def set_policy(policy: dict, user=Depends(get_current_user)):
    db.set_user_policy(user["id"], policy)
    return {"ok": True}


@router.get("/promotion-candidates")
def promotion_candidates(user=Depends(get_current_user)):
    """Tools eligible for autonomy promotion based on confirmation history."""
    return find_promotion_candidates(user["id"])


@router.get("/cost")
def get_cost(user=Depends(get_current_user)):
    """Today's integration spend and per-integration breakdown."""
    from datetime import datetime as _dt, timezone as _tz
    day = _dt.now(_tz.utc).strftime("%Y-%m-%d")
    conn = db.get_connection()
    rows = conn.execute(
        "SELECT integration, SUM(cost_usd) AS total, SUM(calls) AS calls "
        "FROM agent_cost_ledger WHERE user_id=? AND day=? GROUP BY integration",
        (user["id"], day),
    ).fetchall()
    conn.close()
    policy = db.get_user_policy(user["id"])
    cap = float(policy.get("daily_cost_cap_usd", 5.0))
    total = sum(float(r["total"] or 0) for r in rows)
    return {
        "day":                  day,
        "total_usd":            round(total, 4),
        "cap_usd":              cap,
        "remaining_usd":        round(max(0, cap - total), 4),
        "cap_reached":          total >= cap,
        "by_integration":       [{"integration": r["integration"], "cost_usd": round(float(r["total"] or 0), 4), "calls": int(r["calls"] or 0)} for r in rows],
    }


@router.put("/cost/cap")
def set_cost_cap(body: dict, user=Depends(get_current_user)):
    """Set the daily cost cap in user policy."""
    cap = float(body.get("cap_usd", 5.0))
    if cap < 0:
        raise HTTPException(status_code=422, detail="cap must be ≥ 0")
    policy = db.get_user_policy(user["id"])
    policy["daily_cost_cap_usd"] = cap
    db.set_user_policy(user["id"], policy)
    return {"ok": True, "cap_usd": cap}


@router.post("/promotion-candidates/{tool_name}/accept")
def accept_promotion(tool_name: str, user=Depends(get_current_user)):
    """Promote a tool to auto-execute in the user's policy."""
    policy = db.get_user_policy(user["id"])
    tools_policy = policy.get("tools") or {}
    tools_policy[tool_name] = "auto"
    policy["tools"] = tools_policy
    db.set_user_policy(user["id"], policy)
    return {"ok": True, "tool": tool_name, "approval": "auto"}
