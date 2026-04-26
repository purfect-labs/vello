import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH: str            = os.environ.get("DB_PATH", "vello.db")
SECRET_KEY: str         = os.environ.get("SECRET_KEY", "change-me-in-production")
KORTEX_API_URL: str     = os.environ.get("KORTEX_API_URL", "https://kortex.flexflows.net/api/v1")
RESEND_API_KEY: str     = os.environ.get("RESEND_API_KEY", "")
BRIEFING_FROM: str      = os.environ.get("BRIEFING_FROM", "Vello <briefing@vello.flexflows.net>")
APP_URL: str            = os.environ.get("APP_URL", "https://vello.flexflows.net")

# LLM provider: "anthropic" (default) or "openai" (any OpenAI-compatible endpoint)
LLM_PROVIDER: str  = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_BASE_URL: str  = os.environ.get("LLM_BASE_URL", "")   # e.g. https://api.together.xyz/v1
LLM_API_KEY: str   = os.environ.get("LLM_API_KEY", "")    # provider key; falls back to ANTHROPIC_API_KEY

# Model names — override per-provider via env
DIALOGUE_MODEL: str = os.environ.get("DIALOGUE_MODEL", "claude-haiku-4-5-20251001")
AGENT_MODEL: str    = os.environ.get("AGENT_MODEL",    "claude-sonnet-4-6")

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

ONBOARDING_SEQUENCE = ["schedule", "work", "fitness"]
