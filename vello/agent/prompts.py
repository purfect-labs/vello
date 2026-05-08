"""
Planner system prompts and meta-tool declarations.

The agent loop calls `complete_with_tools` with the catalog returned by
`build_planner_tools(user_tools)` — that catalog includes the user-facing
home tools PLUS the three terminal pseudo-tools (`finish`, `need_info`,
`defer`) that let the planner end a turn cleanly without tool-use ambiguity.

Why pseudo-tools instead of stop-on-prose:
  Anthropic's tool-use API can return either a tool_use block *or* prose. If
  we let prose mean "finished", a model that just narrates ("Let me start
  by…") prematurely terminates. Forcing the model to call a terminal tool
  makes the contract unambiguous and matches well with multi-turn loops.
"""
from __future__ import annotations

from typing import Optional

# ── Terminal pseudo-tools ────────────────────────────────────────────────────
#
# These three are appended to every planner tool catalog. They are how the
# planner says "I'm done" / "I need more info" / "I'll come back later".

TERMINAL_TOOL_FINISH = {
    "name": "finish",
    "description": (
        "End this planning turn. Use when you have either: (a) executed/"
        "drafted everything required by the trigger; (b) determined nothing "
        "useful is needed right now; or (c) hit a dead end you can articulate."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "One short sentence explaining why this turn is finishing. "
                    "Will be logged on the agent_session and may surface in "
                    "the activity feed. Be specific and concrete; no filler."
                ),
            },
        },
        "required": ["message"],
    },
}

TERMINAL_TOOL_NEED_INFO = {
    "name": "need_info",
    "description": (
        "End the turn because a critical fact is missing and guessing would "
        "produce a bad plan. Prefer this over fabricating arguments."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": (
                    "A single, narrowly-scoped question for the user. Avoid "
                    "asking for information that read_* tools could have "
                    "answered."
                ),
            },
        },
        "required": ["question"],
    },
}

TERMINAL_TOOL_DEFER = {
    "name": "defer",
    "description": (
        "End the turn without acting because the right time hasn't come. "
        "Use for time-sensitive intents (e.g. wait until business hours)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why you're deferring (one short clause).",
            },
            "retry_at": {
                "type": "string",
                "description": (
                    "Optional ISO-8601 timestamp suggesting when to retry. "
                    "Used by the scheduler to re-fire the trigger."
                ),
            },
        },
        "required": ["reason"],
    },
}


def build_planner_tools(user_tools: list[dict]) -> list[dict]:
    """Append terminal pseudo-tools to a user-facing catalog."""
    return [*user_tools, TERMINAL_TOOL_FINISH, TERMINAL_TOOL_NEED_INFO, TERMINAL_TOOL_DEFER]


# ── System prompt ────────────────────────────────────────────────────────────

# Kept terse on purpose. Long prompts cause planners to forget constraints
# halfway through. Every paragraph below is load-bearing — if you find yourself
# adding bullets, ask whether they belong in tool descriptions instead.

PLANNER_SYSTEM_PROMPT = """\
You are Vello, a home-logistics agent. Your job is to keep a household running
quietly: groceries, supplies, vendors, errands, deliveries, recurring chores,
family schedules. You are NOT a chatbot. You do not narrate. You act.

You operate inside a tool-use loop. Each turn:
- You read trigger context, working memory, and any open standing intent.
- You call tools to inspect state and to commit changes.
- You end the turn by calling `finish`, `need_info`, or `defer`.

Hard rules — violating any of these is worse than doing nothing:
1. PREFER PLAYBOOKS. If a matching playbook exists in working memory, run its
   steps; deviate only when context demands it (and explain in `finish`).
2. NEVER fabricate identifiers. If you don't see a vendor_id, member_id,
   item_id in working memory, do not pass one. Call a `read_*` tool first.
3. NEVER guess a person's contact channel or consent. Use `read_household_members`
   and respect the channels/consent that come back. If the channel is missing
   or consent.notify is false, route through a draft, not an auto-action.
4. PREFER SMALL DRAFTS over large ones. One intent per draft. Composite
   actions (e.g. `request_service`) bundle their own sub-steps; don't manually
   chain `draft_message` + `add_to_calendar` for the same intent.
5. RESPECT THE HORIZON. If the right time to act is days away, `defer` with
   `retry_at`. Don't pre-commit reminders the user will forget about.
6. DO NOT REPEAT YOURSELF. The self-eval after this turn checks novelty
   against the last 24h. Resurfacing the same draft twice in a day is
   considered a quality regression.

Trigger types you'll receive:
- morning_review / evening_review — sweep state, surface what needs attention.
- weekly_planning — Sunday-evening planning playbook entry point.
- restock_needed — fired by inventory_decay_scan; act on the named item.
- signal:* — a behavioral signal fired (e.g. signal:large_purchase).
- webhook:* — external event (delivery confirmation, calendar update).
- user_request — freeform user prompt; treat as authoritative intent.
- voice — same as user_request, transcribed audio.
- campaign_resume — you are continuing an existing standing intent.

When in doubt, end with `finish` and a one-sentence explanation of what you
chose to do or not do. Silence is acceptable; noise is not.
"""


def build_user_message(
    trigger_kind: str,
    trigger_payload: dict,
    working_memory_block: str,
    campaign_summary: Optional[str] = None,
) -> str:
    """
    The first user-message in a planner turn. Working memory is rendered as
    a labelled block; trigger context comes first because it sets intent.
    """
    parts: list[str] = []
    parts.append(f"[TRIGGER] {trigger_kind}")
    if trigger_payload:
        import json as _json
        parts.append(f"[TRIGGER_PAYLOAD]\n{_json.dumps(trigger_payload, indent=2)}")
    if campaign_summary:
        parts.append(f"[OPEN_CAMPAIGN]\n{campaign_summary}")
    parts.append(f"[WORKING_MEMORY]\n{working_memory_block}")
    parts.append(
        "Plan the next step. If the trigger requires no action, call `finish` "
        "with a one-sentence explanation."
    )
    return "\n\n".join(parts)


# ── Self-evaluation prompt (Haiku) ───────────────────────────────────────────

SELF_EVAL_SYSTEM_PROMPT = """\
You are Vello's quality auditor. Score the completed agent turn on three
axes. Return ONLY a JSON object:

  {"coherence": 0.0-1.0,
   "satisfaction_estimate": 0.0-1.0,
   "novelty": 0.0-1.0,
   "rationale": "<one short sentence>"}

Axes:
- coherence: did the plan address the trigger? 0 = unrelated. 1 = directly on-target.
- satisfaction_estimate: would the user agree this turn was worth surfacing?
  0 = noise. 1 = clearly useful right now.
- novelty: is this materially different from sessions in the last 24h shown
  in PRIOR_TURNS? 0 = duplicate. 1 = clearly new.

Be ruthless. Most turns score 0.5 or lower on at least one axis.
"""


def build_self_eval_user_message(
    trigger_kind: str,
    plan: list,
    drafts_created: list,
    prior_turns_summary: str,
) -> str:
    import json as _json
    return (
        f"[TRIGGER] {trigger_kind}\n\n"
        f"[PLAN]\n{_json.dumps(plan, indent=2)}\n\n"
        f"[DRAFTS_CREATED]\n{_json.dumps(drafts_created, indent=2)}\n\n"
        f"[PRIOR_TURNS_24H]\n{prior_turns_summary}"
    )
