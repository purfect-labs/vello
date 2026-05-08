"""
Agent orchestration loop.

run_agent_turn(user_id, trigger) is the single entry point. Order of operations:

  1. Open or reuse a household.
  2. Resume any matching open campaign (else start a fresh session).
  3. Build trigger-conditioned working memory.
  4. Plan-act loop with Sonnet tool-use:
       - call complete_with_tools(...) → PlannerStep
       - dispatch on kind: tool_call / finish / need_info / defer
       - on tool_call: validate → approval → execute or draft → echo result
       - max 6 iterations, then force-finish.
  5. Self-evaluate (Haiku). Suppress drafts on low quality.
  6. Commit session + log.

This module contains the only piece of meaningful runtime control flow in
Vello v2. Every other module is a function library used by this loop. Keep
the surface small.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from vello import database as db
from vello.agent import approval as approval_engine
from vello.agent import campaigns as campaign_store
from vello.agent import memory as memory_builder
from vello.agent import prompts
from vello.agent import tools as tool_module
from vello.agent.tools import (
    ToolContext,
    ToolError,
    ToolUnavailable,
    ToolValidationError,
    summarize_for_draft,
)
from vello.config import AGENT_MODEL, DIALOGUE_MODEL
from vello.llm import PlannerStep, complete, complete_with_tools

log = logging.getLogger(__name__)

MAX_PLANNER_STEPS = 6
DEFAULT_PLANNER_MAX_TOKENS = 1500

# Quality bar: drafts surface only when both thresholds are met.
QUALITY_COHERENCE_MIN = 0.5
QUALITY_NOVELTY_MIN = 0.3


@dataclass
class AgentTurnResult:
    session_id:        str
    outcome:           str            # success | drafted | need_info | deferred | max_steps | error | suppressed
    steps:             int
    drafts_created:    list[dict]    = field(default_factory=list)
    tool_calls:        list[dict]    = field(default_factory=list)
    finish_message:    Optional[str] = None
    need_info:         Optional[str] = None
    defer_reason:      Optional[str] = None
    defer_retry_at:    Optional[str] = None
    quality:           Optional[dict] = None
    campaign_id:       Optional[str] = None


def run_agent_turn(
    user_id: str,
    trigger_kind: str,
    trigger_payload: Optional[dict] = None,
    *,
    suppress_self_eval: bool = False,
) -> AgentTurnResult:
    """
    Execute one agent turn. Synchronous — schedulers and request handlers can
    wrap it as needed. Idempotent at the session level (each call creates a
    new session row), and safe to invoke from any trigger source.
    """
    payload = trigger_payload or {}

    household = db.get_or_create_household(user_id)
    household_id = household["id"]

    # 1. Resume an open campaign if one matches this trigger.
    campaign = campaign_store.find_matching_open(user_id, trigger_kind, payload)
    campaign_id = campaign["id"] if campaign else None
    campaign_summary = campaign_store.render_summary(campaign) if campaign else None

    # 2. Open the session row up front so partial work is recorded even on
    #    crash. We commit outcome/steps at the end.
    session_id = db.create_agent_session(
        user_id=user_id,
        household_id=household_id,
        trigger_kind=trigger_kind,
        trigger_payload=payload,
        campaign_id=campaign_id,
    )

    ctx = ToolContext(user_id=user_id, household_id=household_id, session_id=session_id)

    # 3. Build working memory once. (Tools may write during the turn but the
    #    planner sees the snapshot at start — re-fetching every step is too
    #    chatty for a 6-step budget.)
    wm_block = memory_builder.build_working_memory(
        user_id=user_id,
        household_id=household_id,
        trigger_kind=trigger_kind,
        trigger_payload=payload,
        open_campaign_id=campaign_id,
    )
    presence = memory_builder.build_presence(user_id, household_id)

    # 4. Compose the initial planner messages in Anthropic tool-use shape.
    user_first = prompts.build_user_message(
        trigger_kind=trigger_kind,
        trigger_payload=payload,
        working_memory_block=wm_block,
        campaign_summary=campaign_summary,
    )
    messages: list[dict] = [{"role": "user", "content": user_first}]

    policy = db.get_user_policy(user_id)
    blocked = set(policy.get("data_classes_blocked") or [])
    allowed_classes = {"internal", "third_party", "kortex"} - blocked
    user_tools = tool_module.for_planner(user_id, allowed_data_classes=allowed_classes)
    catalog = prompts.build_planner_tools(user_tools)

    # ── Loop ──────────────────────────────────────────────────────────────
    plan_record: list[dict] = []
    drafts_created: list[dict] = []
    tool_call_records: list[dict] = []
    outcome = "success"
    finish_message = None
    need_info_question = None
    defer_reason = None
    defer_retry_at = None
    last_validation_error: Optional[str] = None

    for step in range(MAX_PLANNER_STEPS):
        try:
            ps = complete_with_tools(
                system=prompts.PLANNER_SYSTEM_PROMPT,
                messages=messages,
                tools=catalog,
                model=AGENT_MODEL,
                max_tokens=DEFAULT_PLANNER_MAX_TOKENS,
            )
        except Exception as exc:
            log.exception("planner call failed in session %s step %d", session_id, step)
            outcome = "error"
            finish_message = f"planner error: {exc}"
            plan_record.append({"step": step, "kind": "planner_error", "error": str(exc)})
            break

        plan_record.append({
            "step":      step,
            "kind":      ps.kind,
            "tool_name": ps.tool_name,
            "raw_text":  ps.raw_text,
            "usage":     ps.usage,
        })

        # ── Terminal kinds short-circuit the loop ────────────────────────
        if ps.kind == "finish":
            finish_message = ps.message or "(no message)"
            outcome = "drafted" if drafts_created else "success"
            break
        if ps.kind == "need_info":
            need_info_question = ps.question or ""
            outcome = "need_info"
            break
        if ps.kind == "defer":
            defer_reason = ps.reason or ""
            defer_retry_at = ps.retry_at
            outcome = "deferred"
            break

        # ── Tool call ─────────────────────────────────────────────────────
        tool_name = ps.tool_name or ""
        tool_input = ps.tool_input or {}
        tool_use_id = ps.tool_use_id

        # Validate args once. On failure, give the planner one feedback step
        # before giving up — the model often fixes simple shape issues.
        try:
            tool = tool_module.get_tool(tool_name)
            if tool is None:
                raise ToolValidationError(f"unknown tool: {tool_name}")
            tool_module._validate_args(tool, tool_input)  # uses internal validator
        except ToolValidationError as exc:
            err_text = str(exc)
            log.info("validation failed in session %s: %s", session_id, err_text)
            db.record_tool_call(
                session_id, step, tool_name, tool_input, None,
                approval="deny", error_text=err_text,
            )
            tool_call_records.append({
                "tool": tool_name, "approval": "deny", "error": err_text,
            })
            if last_validation_error is None:
                # Echo a tool_result error and let the planner retry once.
                last_validation_error = err_text
                _append_assistant_tool_use(messages, ps, tool_name, tool_input)
                _append_user_tool_result(messages, tool_use_id,
                                         {"error": "validation_failed", "detail": err_text},
                                         is_error=True)
                continue
            else:
                # Already retried; abort.
                outcome = "error"
                finish_message = f"persistent validation failure: {err_text}"
                break

        # Approval decision.
        decision = approval_engine.decide_approval(
            tool_name=tool_name, args=tool_input, user_id=user_id, presence=presence,
        )

        # Execute or draft.
        result_for_planner: dict
        error_text: Optional[str] = None
        if decision.approval == "auto":
            try:
                result = tool_module.dispatch(tool_name, tool_input, ctx)
                result_for_planner = result
                tool_call_records.append({
                    "tool": tool_name, "approval": "auto", "result_keys": list(result.keys()),
                })
                db.record_tool_call(
                    session_id, step, tool_name, tool_input, result,
                    approval="auto",
                )
            except ToolUnavailable as exc:
                error_text = str(exc)
                result_for_planner = {"unavailable": True, "detail": error_text}
                tool_call_records.append({
                    "tool": tool_name, "approval": "auto", "unavailable": error_text,
                })
                db.record_tool_call(
                    session_id, step, tool_name, tool_input, result_for_planner,
                    approval="auto", error_text=error_text,
                )
            except ToolError as exc:
                error_text = str(exc)
                result_for_planner = {"error": error_text}
                tool_call_records.append({
                    "tool": tool_name, "approval": "auto", "error": error_text,
                })
                db.record_tool_call(
                    session_id, step, tool_name, tool_input, result_for_planner,
                    approval="auto", error_text=error_text,
                )
            except Exception as exc:
                # Defensive — any unexpected error becomes a structured tool error
                # the planner can route around.
                log.exception("tool %s raised unexpectedly in session %s", tool_name, session_id)
                error_text = f"unexpected_error: {exc}"
                result_for_planner = {"error": error_text}
                tool_call_records.append({
                    "tool": tool_name, "approval": "auto", "error": error_text,
                })
                db.record_tool_call(
                    session_id, step, tool_name, tool_input, result_for_planner,
                    approval="auto", error_text=error_text,
                )
        elif decision.approval == "draft":
            summary = summarize_for_draft(tool_name, tool_input)
            draft_id = db.create_draft(
                user_id=user_id,
                session_id=session_id,
                tool_name=tool_name,
                tool_args=tool_input,
                summary=summary,
            )
            drafts_created.append({
                "id":        draft_id,
                "tool_name": tool_name,
                "summary":   summary,
                "reason":    decision.reason,
            })
            tool_call_records.append({
                "tool": tool_name, "approval": "draft", "reason": decision.reason,
            })
            db.record_tool_call(
                session_id, step, tool_name, tool_input,
                result={"drafted": True, "draft_id": draft_id, "reason": decision.reason},
                approval="draft",
            )
            result_for_planner = {
                "drafted":  True,
                "draft_id": draft_id,
                "summary":  summary,
                "note":     "User will review and confirm before this happens.",
            }
            # Push notification — non-blocking; failure never kills the turn.
            try:
                from vello.push import notify_new_draft
                notify_new_draft(user_id, tool_name, summary)
            except Exception:
                pass
        else:  # deny
            tool_call_records.append({
                "tool": tool_name, "approval": "deny", "reason": decision.reason,
            })
            db.record_tool_call(
                session_id, step, tool_name, tool_input,
                result={"denied": True, "reason": decision.reason},
                approval="deny", error_text=decision.reason,
            )
            result_for_planner = {
                "denied": True,
                "reason": decision.reason,
                "note":   "Pick a different approach or call `finish`.",
            }

        # Echo to planner — required for tool-use multi-turn.
        _append_assistant_tool_use(messages, ps, tool_name, tool_input)
        _append_user_tool_result(
            messages, tool_use_id, result_for_planner,
            is_error=bool(error_text),
        )

    else:
        # for/else fires only when the loop completes without break — that
        # means we hit MAX_PLANNER_STEPS without a terminal kind.
        outcome = "max_steps"
        finish_message = "max planner steps reached"

    # 5. Self-evaluate. Cheap (Haiku). Skipped on error/need_info/deferred —
    #    those don't produce drafts to suppress.
    quality: Optional[dict] = None
    if drafts_created and outcome in ("success", "drafted") and not suppress_self_eval:
        quality = _self_evaluate(user_id, trigger_kind, plan_record, drafts_created)
        if quality and not _passes_quality_bar(quality):
            # Suppress drafts: mark them dismissed silently. They never
            # surface, and tool_stats stay clean (no negative signal).
            for d in drafts_created:
                db.update_draft_status(d["id"], status="dismissed",
                                        error_text="suppressed_low_quality")
            outcome = "suppressed"

    # 6. Append a campaign step if we resumed one.
    if campaign_id and outcome in ("success", "drafted"):
        db.append_campaign_step(
            campaign_id=campaign_id,
            session_id=session_id,
            summary=finish_message or f"step in {trigger_kind}",
        )

    # 7. Commit session.
    db.commit_agent_session(
        session_id=session_id,
        outcome=outcome,
        steps=len(plan_record),
        plan=plan_record,
        quality=quality,
    )

    # Audit log breadcrumb so action_log gets every turn.
    db.log_action(
        user_id=user_id,
        action_type="agent_turn",
        description=f"trigger={trigger_kind} outcome={outcome} drafts={len(drafts_created)}",
        payload={
            "session_id":   session_id,
            "trigger_kind": trigger_kind,
            "outcome":      outcome,
            "campaign_id":  campaign_id,
            "drafts":       [d["id"] for d in drafts_created],
        },
    )

    return AgentTurnResult(
        session_id=session_id,
        outcome=outcome,
        steps=len(plan_record),
        drafts_created=drafts_created,
        tool_calls=tool_call_records,
        finish_message=finish_message,
        need_info=need_info_question,
        defer_reason=defer_reason,
        defer_retry_at=defer_retry_at,
        quality=quality,
        campaign_id=campaign_id,
    )


# ── Tool-use message plumbing ────────────────────────────────────────────────
#
# Anthropic's tool-use API requires the assistant turn to include a `tool_use`
# block (not just text), and the next user turn to include a `tool_result`
# block referencing the same tool_use_id. We mirror that exactly so the
# planner's context isn't truncated by ad-hoc encodings.

def _append_assistant_tool_use(
    messages: list[dict],
    ps: PlannerStep,
    tool_name: str,
    tool_input: dict,
) -> None:
    blocks: list[dict] = []
    if ps.raw_text:
        blocks.append({"type": "text", "text": ps.raw_text})
    blocks.append({
        "type":  "tool_use",
        "id":    ps.tool_use_id or _synth_tool_use_id(tool_name, len(messages)),
        "name":  tool_name,
        "input": tool_input,
    })
    messages.append({"role": "assistant", "content": blocks})


def _append_user_tool_result(
    messages: list[dict],
    tool_use_id: Optional[str],
    result: dict,
    is_error: bool = False,
) -> None:
    if not tool_use_id:
        # Should be unreachable on Anthropic; defensive for OpenAI-compat.
        tool_use_id = _synth_tool_use_id("synth", len(messages))
    block: dict = {
        "type":         "tool_result",
        "tool_use_id":  tool_use_id,
        "content":      json.dumps(result),
    }
    if is_error:
        block["is_error"] = True
    messages.append({"role": "user", "content": [block]})


def _synth_tool_use_id(name: str, idx: int) -> str:
    return f"synth_{name}_{idx}"


# ── Self-eval ────────────────────────────────────────────────────────────────

def _self_evaluate(
    user_id: str,
    trigger_kind: str,
    plan_record: list[dict],
    drafts_created: list[dict],
) -> Optional[dict]:
    """
    Cheap Haiku call. Returns None on failure — we don't want self-eval
    errors to kill a turn.
    """
    prior_summary = _summarize_recent_sessions(user_id, hours=24)
    user_msg = prompts.build_self_eval_user_message(
        trigger_kind=trigger_kind,
        plan=plan_record,
        drafts_created=drafts_created,
        prior_turns_summary=prior_summary,
    )
    try:
        text = complete(
            system=prompts.SELF_EVAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            model=DIALOGUE_MODEL,
            max_tokens=200,
        )
        text = text.strip()
        # Tolerate fenced code blocks the model occasionally adds.
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text[: text.rfind("```")]
        scored = json.loads(text)
        # Coerce numeric ranges 0..1
        for key in ("coherence", "satisfaction_estimate", "novelty"):
            v = scored.get(key)
            try:
                fv = float(v)
            except (TypeError, ValueError):
                fv = 0.5
            scored[key] = max(0.0, min(1.0, fv))
        return scored
    except Exception as exc:
        log.warning("self-eval failed for user %s: %s", user_id, exc)
        return None


def _passes_quality_bar(quality: dict) -> bool:
    return (
        float(quality.get("coherence", 0.0)) >= QUALITY_COHERENCE_MIN
        and float(quality.get("novelty", 0.0)) >= QUALITY_NOVELTY_MIN
    )


def _summarize_recent_sessions(user_id: str, hours: int = 24) -> str:
    """Compact rendering of the last N hours of agent sessions for novelty check."""
    rows = db.list_agent_sessions(user_id, limit=20)
    if not rows:
        return "(none)"
    from datetime import datetime as _dt, timedelta, timezone as _tz
    cutoff = (_dt.now(_tz.utc) - timedelta(hours=hours)).isoformat()
    recent = [r for r in rows if (r["started_at"] or "") > cutoff]
    if not recent:
        return "(none in last 24h)"
    lines = []
    for r in recent[:10]:
        try:
            plan = json.loads(r["plan_json"] or "[]")
        except (ValueError, TypeError):
            plan = []
        tools_used = sorted({step.get("tool_name") for step in plan
                              if step.get("tool_name") and step.get("kind") == "tool_call"})
        lines.append(
            f"- {r['trigger_kind']} → outcome={r['outcome']} tools={list(tools_used)}"
        )
    return "\n".join(lines)
