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
"""
from vello.config import LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, ANTHROPIC_API_KEY


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


# ── Anthropic ──────────────────────────────────────────────────────────────────

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


# ── OpenAI-compatible (Hermes, Llama, etc.) ────────────────────────────────────

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
