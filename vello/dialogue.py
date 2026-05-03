"""
Vello dialogue engine — conversational profile building via Claude.
Extracts structured life context from natural conversation.
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional

from vello.config import DIALOGUE_MODEL
from vello.database import (
    context_as_text, get_dialogue_history, upsert_context,
    save_dialogue_turn, mark_onboarding_complete,
)
from vello.llm import complete

SYSTEM_PROMPT = """\
You are Vello, a personal life agent. You're having a conversation to understand \
this person's daily rhythms and routines — so you can help proactively, without being asked.

Be warm but brief. Ask one question at a time. Confirm what you've learned naturally. \
Never pry — if someone skips, move on gracefully. Sound like a capable person, not a form.

Current context about this user:
{context}

Respond ONLY with valid JSON — no markdown, no extra text:
{{
  "message": "Your conversational response",
  "extracted": [
    {{"domain": "...", "key": "...", "value": "...", "confidence": 0.0}}
  ],
  "suggest_next": "schedule|work|fitness|people|home|finance|health|preferences|null",
  "onboarding_complete": false
}}

Extractable domains and keys:
- schedule: wake_time, sleep_goal, work_start, work_end, commute_type, commute_minutes
- fitness: goal, workout_days, workout_time, gym_location, weekly_target, activities
- work: location_type, hybrid_days, meeting_style
- people: partner_name, partner_phone, partner_notify_mode
- home: home_type, occupant_count, smart_home_platform
- finance: auto_spend_limit
- health: sleep_quality_goal, dietary_notes
- preferences: brief_style, quiet_start, quiet_end

Set onboarding_complete=true only after covering schedule, work, and fitness basics. \
Once complete, tell the user warmly that they're all set and Vello will learn the rest.\
"""

ONBOARDING_OPENER = """\
You are Vello starting your very first conversation with a new user. \
Greet them briefly, explain in one sentence what you do, then ask your first question: \
what time do they usually wake up on weekdays. Keep it light.\
"""


def _build_messages(history: list, user_message: str) -> list:
    messages = []
    for turn in history[-10:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def _parse_response(raw: str) -> dict:
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"```[a-z]*\n?", "", cleaned).strip("`").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"message": raw, "extracted": [], "suggest_next": None, "onboarding_complete": False}


def _is_first_message_today(history: list) -> bool:
    """True if no prior turns exist for today (UTC)."""
    today = datetime.now(timezone.utc).date().isoformat()
    return not any(t["created_at"].startswith(today) for t in history)


def chat(user_id: str, user_message: str, is_first_message: bool = False) -> dict:
    """
    Process a user message, extract any life context, persist it, and return the reply.
    Returns: {"message": str, "suggest_next": str|None, "onboarding_complete": bool}
    """
    history = get_dialogue_history(user_id, limit=20)
    context = context_as_text(user_id)

    system = SYSTEM_PROMPT.format(context=context or "Nothing known yet.")
    if is_first_message:
        system += f"\n\n{ONBOARDING_OPENER}"

    messages = _build_messages(history, user_message)

    raw = complete(system, messages, model=DIALOGUE_MODEL, max_tokens=600)
    parsed = _parse_response(raw)

    assistant_message = parsed.get("message", raw)
    extracted = parsed.get("extracted") or []
    onboarding_done = parsed.get("onboarding_complete", False)

    save_dialogue_turn(user_id, "user", user_message)
    save_dialogue_turn(user_id, "assistant", assistant_message)

    for item in extracted:
        if item.get("domain") and item.get("key") and item.get("value"):
            upsert_context(
                user_id,
                domain=item["domain"],
                key=item["key"],
                value=str(item["value"]),
                source="conversation",
                confidence=float(item.get("confidence", 0.8)),
            )

    if onboarding_done:
        mark_onboarding_complete(user_id)

    # ── Infer wake_time from first message of the day ──────────────────────────
    # Only counts a "first message" as a wake-time observation if it lands in a
    # plausible morning window in the user's local timezone. A night-owl
    # messaging at 1am shouldn't poison the wake_time pattern.
    if user_message != "__init__" and _is_first_message_today(history):
        try:
            from vello.temporal import log_observation, user_local_now, WAKE_WINDOW
            now_local = user_local_now(user_id)
            minutes = now_local.hour * 60 + now_local.minute
            wake_min, wake_max = WAKE_WINDOW
            if wake_min <= minutes <= wake_max:
                log_observation(user_id, "wake_time", "Wake time", minutes)
        except Exception:
            pass

    # ── Run signal detection on user message ───────────────────────────────────
    if user_message != "__init__":
        try:
            from vello.signals import fire_signals
            fire_signals(user_id, user_message)
        except Exception:
            pass

    return {
        "message": assistant_message,
        "extracted": extracted,
        "suggest_next": parsed.get("suggest_next"),
        "onboarding_complete": onboarding_done,
    }
