"""
Unified LLM completion layer.

Set LLM_PROVIDER=anthropic (default) to use Claude via the Anthropic SDK.
Set LLM_PROVIDER=openai to use any OpenAI-compatible endpoint — Hermes via
Together AI / Fireworks / Ollama, local vLLM, etc.

  # Hermes-3 on Together AI
  LLM_PROVIDER=openai
  LLM_BASE_URL=https://api.together.xyz/v1
  LLM_API_KEY=<together-key>
  DIALOGUE_MODEL=NousResearch/Hermes-3-Llama-3.1-8B
  AGENT_MODEL=NousResearch/Hermes-3-Llama-3.1-70B

  # Hermes via Ollama (local)
  LLM_PROVIDER=openai
  LLM_BASE_URL=http://localhost:11434/v1
  LLM_API_KEY=ollama
  DIALOGUE_MODEL=hermes3
  AGENT_MODEL=hermes3:70b

This module exposes two completion entrypoints:

  complete()             — plain text completion (used by dialogue, signal
                           extraction, briefing copy, self-eval).
  complete_with_tools()  — tool-use loop step. Returns a structured
                           PlannerStep that the agent loop interprets.

`complete_with_tools` uses Anthropic's first-class tool-use API when
LLM_PROVIDER=anthropic. For OpenAI-compatible backends without proper
tool-use (Hermes etc.), it falls back to JSON-mode prompting — less
reliable, but the contract is identical so the agent loop doesn't care.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from vello.config import LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, ANTHROPIC_API_KEY

log = logging.getLogger(__name__)


def complete(system: str, messages: list[dict], model: str, max_tokens: int = 600) -> str:
    """
    Send a completion request and return the assistant text.

    `messages` follows the Anthropic/OpenAI shared convention:
        [{"role": "user"|"assistant", "content": "..."}]
    The `system` prompt is passed separately so it works identically with both SDKs.
    """
    if LLM_PROVIDER == "openai":
        return _openai_complete(system, messages, model, max_tokens)
    return _anthropic_complete(system, messages, model, max_tokens)


# ── Anthropic plain ───────────────────────────────────────────────────────────

def _anthropic_complete(system: str, messages: list[dict], model: str, max_tokens: int) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    r = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return r.content[0].text


# ── OpenAI-compatible plain ──────────────────────────────────────────────────

def _openai_complete(system: str, messages: list[dict], model: str, max_tokens: int) -> str:
    import openai
    api_key = LLM_API_KEY or ANTHROPIC_API_KEY or "placeholder"
    kwargs: dict = {"api_key": api_key}
    if LLM_BASE_URL:
        kwargs["base_url"] = LLM_BASE_URL
    client = openai.OpenAI(**kwargs)

    # OpenAI chat format: system as first message
    oai_messages = [{"role": "system", "content": system}] + messages

    r = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=oai_messages,
    )
    return r.choices[0].message.content or ""


# ─────────────────────────────────────────────────────────────────────────────
# Tool-use planner contract
# ─────────────────────────────────────────────────────────────────────────────
#
# The agent loop calls `complete_with_tools` after each tool execution. It
# passes the system prompt, the running message history (which includes prior
# tool calls + their results, encoded for Anthropic's tool-use protocol), and
# the catalog of currently-available tools.
#
# The model returns *exactly one* of:
#
#   - a tool call  → kind="tool_call", tool_name=…, tool_input=…
#   - finish        → kind="finish", message=…   (terminal)
#   - need_info     → kind="need_info", question=…   (terminal)
#   - defer         → kind="defer", reason=…, retry_at=…   (terminal)
#
# need_info / defer are first-class outcomes — they prevent the "agent
# guesses confidently and is wrong" failure mode.
#
# The tool catalog item shape is:
#   {"name": "...", "description": "...", "input_schema": {<JSON schema>}}
#
# That maps 1:1 to Anthropic's tool-use API.

@dataclass
class PlannerStep:
    kind: str                                    # tool_call | finish | need_info | defer
    tool_name: Optional[str] = None
    tool_input: dict = field(default_factory=dict)
    tool_use_id: Optional[str] = None            # Anthropic id for tool_result echo
    message: Optional[str] = None                # finish message
    question: Optional[str] = None               # need_info question
    reason: Optional[str] = None                 # defer reason
    retry_at: Optional[str] = None               # defer ISO timestamp
    raw_text: Optional[str] = None               # planner's narration if any
    stop_reason: Optional[str] = None
    usage: Optional[dict] = None                 # token counts when available


def complete_with_tools(
    system: str,
    messages: list[dict],
    tools: list[dict],
    model: str,
    max_tokens: int = 1500,
) -> PlannerStep:
    """
    Single planner turn against the tool catalog. Returns a PlannerStep the
    agent loop can dispatch on.

    `messages` MUST follow Anthropic's tool-use format: assistant turns may
    contain `tool_use` blocks; user turns may contain `tool_result` blocks.
    The agent loop is responsible for appending these as it iterates. We keep
    the wire format here rather than abstracting it because losing fidelity
    breaks tool-use multi-turn.

    For OpenAI-compatible backends we degrade to JSON-mode prompting —
    `messages` is flattened to plain text and the model is asked to respond
    with a single JSON object matching the PlannerStep schema. Less reliable,
    but the loop's contract stays the same.
    """
    if LLM_PROVIDER == "openai":
        return _openai_plan_with_tools(system, messages, tools, model, max_tokens)
    return _anthropic_plan_with_tools(system, messages, tools, model, max_tokens)


def _anthropic_plan_with_tools(
    system: str,
    messages: list[dict],
    tools: list[dict],
    model: str,
    max_tokens: int,
) -> PlannerStep:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=tools,
        messages=messages,
    )

    # Collect text + tool_use blocks. Anthropic returns content as a list.
    text_chunks: list[str] = []
    tool_uses: list[Any] = []
    for block in resp.content or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            text_chunks.append(getattr(block, "text", "") or "")
        elif btype == "tool_use":
            tool_uses.append(block)

    raw_text = "".join(text_chunks).strip() or None
    usage = getattr(resp, "usage", None)
    usage_dict: Optional[dict] = None
    if usage is not None:
        usage_dict = {
            "input_tokens":  getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
        }

    if tool_uses:
        # We process exactly one tool call per planner step. The agent loop
        # will echo a tool_result for it, then call us again.
        tu = tool_uses[0]
        # Distinguish our terminal pseudo-tools (finish/need_info/defer) from
        # real tool calls. Pseudo-tools must be in `tools` with names matching
        # the sentinels below — see prompts.py for how they're declared.
        name = getattr(tu, "name", "")
        tinput = getattr(tu, "input", {}) or {}
        tu_id = getattr(tu, "id", None)
        if name == "finish":
            return PlannerStep(
                kind="finish",
                message=str(tinput.get("message", "")),
                tool_use_id=tu_id,
                raw_text=raw_text,
                stop_reason=getattr(resp, "stop_reason", None),
                usage=usage_dict,
            )
        if name == "need_info":
            return PlannerStep(
                kind="need_info",
                question=str(tinput.get("question", "")),
                tool_use_id=tu_id,
                raw_text=raw_text,
                stop_reason=getattr(resp, "stop_reason", None),
                usage=usage_dict,
            )
        if name == "defer":
            return PlannerStep(
                kind="defer",
                reason=str(tinput.get("reason", "")),
                retry_at=tinput.get("retry_at"),
                tool_use_id=tu_id,
                raw_text=raw_text,
                stop_reason=getattr(resp, "stop_reason", None),
                usage=usage_dict,
            )
        return PlannerStep(
            kind="tool_call",
            tool_name=name,
            tool_input=dict(tinput),
            tool_use_id=tu_id,
            raw_text=raw_text,
            stop_reason=getattr(resp, "stop_reason", None),
            usage=usage_dict,
        )

    # No tool call — model finished with prose.
    return PlannerStep(
        kind="finish",
        message=raw_text or "",
        raw_text=raw_text,
        stop_reason=getattr(resp, "stop_reason", None),
        usage=usage_dict,
    )


def _openai_plan_with_tools(
    system: str,
    messages: list[dict],
    tools: list[dict],
    model: str,
    max_tokens: int,
) -> PlannerStep:
    """
    JSON-mode fallback. Flattens history into a prompt and asks for a single
    JSON object. Tool reliability is lower than native tool-use; we surface
    obvious shape errors as `defer` so the loop can give up cleanly.
    """
    import openai
    api_key = LLM_API_KEY or ANTHROPIC_API_KEY or "placeholder"
    kwargs: dict = {"api_key": api_key}
    if LLM_BASE_URL:
        kwargs["base_url"] = LLM_BASE_URL
    client = openai.OpenAI(**kwargs)

    flat = _flatten_anthropic_messages(messages)
    catalog = json.dumps(
        [{"name": t["name"], "description": t.get("description", ""),
          "input_schema": t.get("input_schema", {})}
         for t in tools],
        indent=2,
    )
    contract_system = (
        f"{system}\n\n"
        "You MUST respond with a single JSON object — no prose. Schema:\n"
        '{"kind": "tool_call"|"finish"|"need_info"|"defer", '
        '"tool_name"?: str, "tool_input"?: object, '
        '"message"?: str, "question"?: str, "reason"?: str, "retry_at"?: str}\n'
        "tool_call requires tool_name + tool_input matching one of the tools.\n"
        f"Available tools (JSON schema):\n{catalog}"
    )
    oai_messages = [
        {"role": "system", "content": contract_system},
        {"role": "user", "content": flat},
    ]

    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=oai_messages,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        log.warning("openai-compat tool-use call failed: %s", exc)
        return PlannerStep(kind="defer", reason=f"planner_error: {exc}")

    body = resp.choices[0].message.content or ""
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return PlannerStep(kind="defer", reason="planner_returned_non_json", raw_text=body)

    kind = parsed.get("kind")
    if kind == "tool_call":
        return PlannerStep(
            kind="tool_call",
            tool_name=parsed.get("tool_name"),
            tool_input=parsed.get("tool_input") or {},
            raw_text=body,
        )
    if kind == "finish":
        return PlannerStep(kind="finish", message=parsed.get("message", ""), raw_text=body)
    if kind == "need_info":
        return PlannerStep(kind="need_info", question=parsed.get("question", ""), raw_text=body)
    if kind == "defer":
        return PlannerStep(
            kind="defer",
            reason=parsed.get("reason", ""),
            retry_at=parsed.get("retry_at"),
            raw_text=body,
        )
    return PlannerStep(kind="defer", reason=f"unknown_kind: {kind!r}", raw_text=body)


def _flatten_anthropic_messages(messages: list[dict]) -> str:
    """
    Render Anthropic-shaped tool-use history into a single human-readable
    prompt for OpenAI-compat backends that lack tool-use support.
    """
    out: list[str] = []
    for msg in messages:
        role = msg.get("role", "user").upper()
        content = msg.get("content")
        if isinstance(content, str):
            out.append(f"[{role}] {content}")
            continue
        if isinstance(content, list):
            for block in content:
                btype = block.get("type") if isinstance(block, dict) else None
                if btype == "text":
                    out.append(f"[{role}] {block.get('text', '')}")
                elif btype == "tool_use":
                    out.append(
                        f"[{role}] CALL {block.get('name')} "
                        f"INPUT={json.dumps(block.get('input', {}))}"
                    )
                elif btype == "tool_result":
                    rc = block.get("content")
                    txt = rc if isinstance(rc, str) else json.dumps(rc)
                    out.append(f"[{role}] TOOL_RESULT {txt}")
    return "\n".join(out)
