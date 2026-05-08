"""
Approval engine — decides whether a tool call auto-executes, gets drafted
for user confirmation, or is denied outright.

Decision precedence (each step short-circuits the rest):

  1. Tier 4 hard floor — irreversible/cost tools never auto.
  2. Data-class veto    — user blocks `third_party` or `kortex` outbound.
  3. User policy override — explicit per-tool setting wins inside its tier.
  4. Learned demotion   — recent dismissal pattern forces draft.
  5. Learned promotion  — earned trust + tier ≤ 3 lifts to auto.
  6. Circuit breakers   — recent errors / cost cap → deny or draft.
  7. Member consent     — tools targeting a member without consent.notify
                          are denied unless drafting is fine for the tier.
  8. Tier default       — Tier 1/2 = auto; Tier 3 = draft; Tier 4 = draft.

Why this order: safety floors first, user intent second, learned signals
third. Mechanical rate-limits (cost / errors) come AFTER policy so that an
explicit "deny this tool" stays denied even if the breaker would have
allowed it. Tier defaults are last so they only apply when nothing more
specific decided.

Decision dataclass carries a `reason` so the agent loop can log *why* a
particular outcome was chosen — important for debugging and for the
"Vello did" feed UX.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from vello import database as db
from vello.agent.tools import Tool, get_tool

log = logging.getLogger(__name__)


# Tunables — exposed as constants so tests can import and tweak.
PROMOTION_MIN_OUTCOMES = 20
PROMOTION_CONFIRM_RATIO = 0.85
DEMOTION_DISMISSALS_7D = 3
CIRCUIT_BREAKER_ERRORS_1H = 3
DEFAULT_DAILY_COST_CAP_USD = 5.0


@dataclass
class Decision:
    approval: str               # "auto" | "draft" | "deny"
    reason:   str               # short tag like "tier4_floor", "policy_override:auto"

    @property
    def is_auto(self) -> bool:
        return self.approval == "auto"


def decide_approval(
    tool_name: str,
    args: dict,
    user_id: str,
    presence: Optional[dict] = None,
) -> Decision:
    """
    presence (optional): {"home_members": [member_id...], "dnd_until": iso?,
                          "current_local_hour": int?}.
    Loop builds it once per turn and reuses it for every approval check.
    """
    tool = get_tool(tool_name)
    if tool is None:
        return Decision(approval="deny", reason="unknown_tool")

    policy = db.get_user_policy(user_id)

    # ── 1. Tier 4 hard floor ──────────────────────────────────────────────
    if tool.tier >= 4:
        # Tier 4 is always drafted, never denied unless circuit-broken.
        cb = _circuit_breaker(tool, user_id, policy)
        if cb is not None:
            return cb
        return Decision(approval="draft", reason="tier4_floor")

    # ── 2. Data-class veto ────────────────────────────────────────────────
    blocked_classes = set(policy.get("data_classes_blocked") or [])
    if tool.data_class in blocked_classes:
        return Decision(
            approval="deny",
            reason=f"data_class_blocked:{tool.data_class}",
        )

    # ── 3. User policy override ───────────────────────────────────────────
    tool_policy = (policy.get("tools") or {}).get(tool_name)
    if tool_policy in ("auto", "draft", "deny"):
        # Even an explicit "auto" override has to pass safety floors.
        if tool_policy == "auto" and tool.tier >= 4:
            tool_policy = "draft"  # already handled above, but defensive
        # Member consent must still block notifications even on auto policy.
        consent_check = _consent_check(tool, args, tool_policy)
        if consent_check is not None:
            return consent_check
        if tool_policy == "auto":
            cb = _circuit_breaker(tool, user_id, policy)
            if cb is not None:
                return cb
        return Decision(approval=tool_policy, reason=f"policy_override:{tool_policy}")

    # ── 4. Learned demotion ───────────────────────────────────────────────
    dismissals = db.count_recent_dismissals(user_id, tool_name, days=7)
    if dismissals >= DEMOTION_DISMISSALS_7D:
        # Forced to draft regardless of tier default — but only if tier
        # already permits external action (drafts mean nothing for tier 1
        # which is auto-read).
        if tool.tier >= 2:
            return Decision(
                approval="draft",
                reason=f"demoted:{dismissals}_dismissals_7d",
            )

    # ── 5. Learned promotion (Tier 3 → auto when trusted) ────────────────
    if tool.tier == 3:
        promoted = _is_promoted(user_id, tool_name)
        if promoted:
            consent_check = _consent_check(tool, args, "auto")
            if consent_check is not None:
                return consent_check
            cb = _circuit_breaker(tool, user_id, policy)
            if cb is not None:
                return cb
            return Decision(approval="auto", reason="trust_promoted")

    # ── 6. Circuit breakers (errors + cost cap) ──────────────────────────
    cb = _circuit_breaker(tool, user_id, policy)
    if cb is not None:
        return cb

    # ── 7. Member consent ─────────────────────────────────────────────────
    consent_check = _consent_check(tool, args, _tier_default(tool.tier))
    if consent_check is not None:
        return consent_check

    # ── 8. Tier default ───────────────────────────────────────────────────
    return Decision(approval=_tier_default(tool.tier), reason=f"tier{tool.tier}_default")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tier_default(tier: int) -> str:
    if tier <= 2:
        return "auto"
    return "draft"


def _is_promoted(user_id: str, tool_name: str) -> bool:
    """Earned auto-execute: enough confirmations, high confirm ratio, no recent errors."""
    rows = db.get_tool_stats(user_id, tool_name=tool_name)
    if not rows:
        return False
    r = rows[0]
    confirmed = int(r["confirmed_count"] or 0)
    dismissed = int(r["dismissed_count"] or 0)
    errors    = int(r["error_count"] or 0)
    total     = confirmed + dismissed
    if total < PROMOTION_MIN_OUTCOMES:
        return False
    if errors > 0:
        # Any hard error in stats invalidates promotion.
        return False
    if (confirmed / max(total, 1)) < PROMOTION_CONFIRM_RATIO:
        return False
    return True


def _circuit_breaker(tool: Tool, user_id: str, policy: dict) -> Optional[Decision]:
    """Returns a denied/drafted Decision if a breaker has tripped, else None."""
    # 6a: tool failures in last hour
    if db.count_recent_tool_errors(user_id, tool.name, hours=1) >= CIRCUIT_BREAKER_ERRORS_1H:
        return Decision(approval="deny", reason="breaker_recent_errors")

    # 6b: per-day integration cost cap
    if tool.cost_usd > 0:
        cap = float(policy.get("daily_cost_cap_usd") or DEFAULT_DAILY_COST_CAP_USD)
        spent = db.get_today_cost(user_id)
        if spent + tool.cost_usd > cap:
            return Decision(approval="deny", reason=f"breaker_cost_cap:{cap:.2f}")
    return None


def _consent_check(tool: Tool, args: dict, default_path: str) -> Optional[Decision]:
    """
    If the tool targets a household member, ensure consent.notify=true for
    auto-paths. For draft paths, drafting is fine — the user reviews before
    anything reaches the member.

    Returns a Decision when this check OVERRIDES the would-be path, else None.
    """
    if default_path != "auto":
        return None  # drafting requires no consent check

    member_id = args.get("recipient_id") or args.get("member_id")
    if not member_id:
        return None

    member = db.get_household_member(member_id)
    if not member:
        # Hallucinated member id → deny so the planner re-plans rather than
        # auto-executing on a phantom recipient.
        return Decision(approval="deny", reason="unknown_member")

    import json as _json
    try:
        consent = _json.loads(member["consent_json"] or "{}") or {}
    except (ValueError, TypeError):
        consent = {}
    if not consent.get("notify", False):
        return Decision(approval="draft", reason="member_no_notify_consent")

    return None


# ── Trust-promotion proposals (called by episodic_consolidation) ─────────────

def find_promotion_candidates(user_id: str) -> list[dict]:
    """
    Identify tool/user pairs that are *eligible* for auto-promotion but the
    policy hasn't yet been changed. The consolidation job uses this to
    surface PromotionPrompt drafts in the inbox — Vello does NOT
    auto-promote without explicit user acceptance.

    Tier 4 tools are never candidates regardless of stats.
    """
    rows = db.get_tool_stats(user_id)
    policy = db.get_user_policy(user_id)
    overrides = (policy.get("tools") or {})

    out: list[dict] = []
    for r in rows:
        tool_name = r["tool_name"]
        tool = get_tool(tool_name)
        if tool is None or tool.tier != 3:
            continue
        if overrides.get(tool_name) == "auto":
            continue  # already promoted
        if not _is_promoted(user_id, tool_name):
            continue
        out.append({
            "tool":      tool_name,
            "confirmed": int(r["confirmed_count"] or 0),
            "dismissed": int(r["dismissed_count"] or 0),
        })
    return out
