"""
Integration connection status + disconnect routes.

GET  /integrations        → list all integration statuses
POST /integrations/twilio → save Twilio number (no OAuth needed, user supplies manually)
DELETE /integrations/{provider} → disconnect (clear stored token)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db
from vello.config import (
    GCAL_CLIENT_ID, TWILIO_ACCOUNT_SID, OPENWEATHER_API_KEY,
    GMAPS_API_KEY, AFTERSHIP_API_KEY,
)

router = APIRouter()


@router.get("/")
def list_integrations(user=Depends(get_current_user)):
    """Returns connection status for each integration."""
    google_token = db.get_oauth_token(user["id"], "google")
    return {
        "google_calendar": {
            "available":  bool(GCAL_CLIENT_ID),
            "connected":  google_token is not None,
            "provider":   "google",
        },
        "twilio_sms": {
            "available": bool(TWILIO_ACCOUNT_SID),
            "connected": bool(TWILIO_ACCOUNT_SID),
            "note":      "Configured via env var — set TWILIO_* in .env",
        },
        "openweather": {
            "available": bool(OPENWEATHER_API_KEY),
            "connected": bool(OPENWEATHER_API_KEY),
            "note":      "Configured via env var — set OPENWEATHER_API_KEY",
        },
        "google_maps": {
            "available": bool(GMAPS_API_KEY),
            "connected": bool(GMAPS_API_KEY),
            "note":      "Configured via env var — set GMAPS_API_KEY",
        },
        "aftership": {
            "available": bool(AFTERSHIP_API_KEY),
            "connected": bool(AFTERSHIP_API_KEY),
            "note":      "Configured via env var — set AFTERSHIP_API_KEY",
        },
    }


@router.delete("/{provider}", status_code=204)
def disconnect(provider: str, user=Depends(get_current_user)):
    """Disconnect an OAuth integration by clearing the stored token."""
    supported_oauth = {"google"}
    if provider not in supported_oauth:
        raise HTTPException(status_code=400, detail=f"provider {provider!r} not OAuth-managed")
    conn = db.get_connection()
    with conn:
        conn.execute(
            "DELETE FROM user_oauth_tokens WHERE user_id=? AND provider=?",
            (user["id"], provider),
        )
    conn.close()
