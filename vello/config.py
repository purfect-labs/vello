import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH: str            = os.environ.get("DB_PATH", "vello.db")
SECRET_KEY: str         = os.environ.get("SECRET_KEY", "change-me-in-production")
KORTEX_API_URL: str     = os.environ.get("KORTEX_API_URL", "https://kortex.flexflows.net/api/v1")

DIALOGUE_MODEL  = "claude-haiku-4-5-20251001"
AGENT_MODEL     = "claude-sonnet-4-6"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

ONBOARDING_SEQUENCE = ["schedule", "work", "fitness"]
