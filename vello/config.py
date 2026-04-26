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

DIALOGUE_MODEL  = "claude-haiku-4-5-20251001"
AGENT_MODEL     = "claude-sonnet-4-6"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

ONBOARDING_SEQUENCE = ["schedule", "work", "fitness"]
