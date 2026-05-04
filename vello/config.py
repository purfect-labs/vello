import os
from dotenv import load_dotenv

load_dotenv()

ENV: str                = os.environ.get("ENV", "development")
ANTHROPIC_API_KEY: str  = os.environ.get("ANTHROPIC_API_KEY", "")
DB_PATH: str            = os.environ.get("DB_PATH", "vello.db")
SECRET_KEY: str         = os.environ.get("SECRET_KEY", "change-me-in-production")
KORTEX_API_URL: str     = os.environ.get("KORTEX_API_URL", "https://kortex.flexflows.net/api/v1")
KORTEX_PUBLIC_KEY_URL: str = os.environ.get(
    "KORTEX_PUBLIC_KEY_URL",
    f"{KORTEX_API_URL}/developer/public-key",
)
# Email (AWS SES via boto3). Sender domain (vello.flexflows.net) must be a
# verified SES identity in AWS_REGION. Production sending requires the SES
# account to be out of sandbox. Runtime credentials come from the standard
# boto3 chain: instance profile on EC2, env vars locally, or ~/.aws/credentials.
AWS_REGION: str         = os.environ.get("AWS_REGION", "us-east-1")
BRIEFING_FROM: str      = os.environ.get("BRIEFING_FROM", "Vello <noreply@vello.flexflows.net>")
APP_URL: str            = os.environ.get("APP_URL", "https://vello.flexflows.net")

# LLM provider: "anthropic" (default) or "openai" (any OpenAI-compatible endpoint)
LLM_PROVIDER: str  = os.environ.get("LLM_PROVIDER", "anthropic")
LLM_BASE_URL: str  = os.environ.get("LLM_BASE_URL", "")   # e.g. https://api.together.xyz/v1
LLM_API_KEY: str   = os.environ.get("LLM_API_KEY", "")    # provider key; falls back to ANTHROPIC_API_KEY

# Model name — override per-provider via env. Dialogue is currently the only
# active LLM call site. An AGENT_MODEL config previously existed for an
# unbuilt Sonnet-driven inference pass; removed in the audit pass to avoid
# implying a feature that doesn't exist. Re-add it here once an inference
# engine actually exists and uses it.
DIALOGUE_MODEL: str = os.environ.get("DIALOGUE_MODEL", "claude-haiku-4-5-20251001")

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days

# Request hardening
MAX_REQUEST_BODY_BYTES: int = int(os.environ.get("MAX_REQUEST_BODY_BYTES", str(1 * 1024 * 1024)))  # 1 MiB
MAX_DIALOGUE_MESSAGE_CHARS: int = int(os.environ.get("MAX_DIALOGUE_MESSAGE_CHARS", "4000"))

ONBOARDING_SEQUENCE = ["schedule", "work", "fitness"]


def validate_config() -> None:
    """Fail fast at startup if security-critical variables are missing or weak."""
    errors: list[str] = []

    if SECRET_KEY in ("", "change-me-in-production", "insecure-dev-key-change-in-production"):
        if ENV == "production":
            errors.append("SECRET_KEY must be overridden in production (never the default)")
    if len(SECRET_KEY) < 32 and ENV == "production":
        errors.append("SECRET_KEY too short (minimum 32 characters in production)")

    if errors:
        raise RuntimeError(
            "Vello configuration errors — fix before starting:\n  " + "\n  ".join(errors)
        )
