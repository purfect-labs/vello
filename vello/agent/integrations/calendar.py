"""
Google Calendar OAuth 2.0 adapter.

Flow:
  1. User clicks "Connect Google Calendar" in Settings.
  2. Frontend redirects to GET /api/v1/auth/oauth/google → returns an auth URL.
  3. Google redirects to GCAL_REDIRECT_URI (/api/v1/auth/oauth/google/callback).
  4. Callback exchanges code for tokens, encrypts + persists via db.set_oauth_token.
  5. Tool calls go through `CalendarClient(user_id)` which auto-refreshes tokens.

Scopes:
  - https://www.googleapis.com/auth/calendar.readonly   (read_calendar)
  - https://www.googleapis.com/auth/calendar.events      (add_to_calendar, cancel_event)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from vello.agent.tools import ToolUnavailable
from vello.config import APP_URL, GCAL_CLIENT_ID, GCAL_CLIENT_SECRET, GCAL_REDIRECT_URI

log = logging.getLogger(__name__)

_AUTH_URL   = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL  = "https://oauth2.googleapis.com/token"
_CAL_BASE   = "https://www.googleapis.com/calendar/v3"
_SCOPES     = "https://www.googleapis.com/auth/calendar"

_COST_PER_READ  = 0.0
_COST_PER_WRITE = 0.001


def _require_credentials() -> None:
    if not GCAL_CLIENT_ID or not GCAL_CLIENT_SECRET:
        raise ToolUnavailable("calendar: GCAL_CLIENT_ID / GCAL_CLIENT_SECRET not set")


def get_auth_url(state: str = "") -> str:
    """Returns the Google OAuth consent URL. Frontend redirects the user here."""
    _require_credentials()
    params = {
        "client_id":     GCAL_CLIENT_ID,
        "redirect_uri":  GCAL_REDIRECT_URI,
        "response_type": "code",
        "scope":         _SCOPES,
        "access_type":   "offline",
        "prompt":        "consent",
    }
    if state:
        params["state"] = state
    from urllib.parse import urlencode
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """
    Exchange an authorization code for access+refresh tokens.
    Returns the raw token response dict.
    """
    _require_credentials()
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(_TOKEN_URL, data={
                "code":          code,
                "client_id":     GCAL_CLIENT_ID,
                "client_secret": GCAL_CLIENT_SECRET,
                "redirect_uri":  GCAL_REDIRECT_URI,
                "grant_type":    "authorization_code",
            })
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolUnavailable(f"calendar: token exchange failed {exc.response.status_code}")
    return r.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Returns new {access_token, expires_in} or raises ToolUnavailable."""
    _require_credentials()
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(_TOKEN_URL, data={
                "refresh_token": refresh_token,
                "client_id":     GCAL_CLIENT_ID,
                "client_secret": GCAL_CLIENT_SECRET,
                "grant_type":    "refresh_token",
            })
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ToolUnavailable(f"calendar: token refresh failed {exc.response.status_code}")
    return r.json()


class CalendarClient:
    """Per-user Calendar client. Lazily loads and refreshes the stored token."""

    def __init__(self, user_id: str):
        self._user_id = user_id
        self._access_token: Optional[str] = None

    def _get_token(self) -> str:
        if self._access_token:
            return self._access_token
        from vello import database as db
        tokens = db.get_oauth_token(self._user_id, "google")
        if not tokens:
            raise ToolUnavailable("read_calendar: Google Calendar not connected — visit Settings to connect")
        access = tokens.get("access_token", "")
        refresh = tokens.get("refresh_token", "")
        expires_at = tokens.get("expires_at", "")

        # Check expiry (refresh 5 min early)
        needs_refresh = False
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt - datetime.now(timezone.utc) < timedelta(minutes=5):
                    needs_refresh = True
            except (ValueError, TypeError):
                needs_refresh = True

        if needs_refresh:
            if not refresh:
                raise ToolUnavailable("read_calendar: access token expired and no refresh token — reconnect in Settings")
            new_tokens = refresh_access_token(refresh)
            access = new_tokens.get("access_token", "")
            if not access:
                raise ToolUnavailable("read_calendar: token refresh returned no access token")
            expires_in = int(new_tokens.get("expires_in", 3600))
            new_exp = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
            db.set_oauth_token(
                self._user_id, "google", access,
                refresh_token=refresh, expires_at=new_exp,
                scopes=tokens.get("scopes"),
            )

        self._access_token = access
        return access

    def _get(self, path: str, params: dict | None = None) -> dict:
        token = self._get_token()
        try:
            with httpx.Client(timeout=15) as client:
                r = client.get(
                    f"{_CAL_BASE}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    params=params or {},
                )
            if r.status_code == 401:
                self._access_token = None  # force re-fetch next call
                raise ToolUnavailable("read_calendar: Google rejected token — reconnect in Settings")
            r.raise_for_status()
        except httpx.RequestError as exc:
            raise ToolUnavailable(f"read_calendar: network error — {exc}")
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        token = self._get_token()
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(
                    f"{_CAL_BASE}{path}",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json"},
                    json=body,
                )
            if r.status_code == 401:
                self._access_token = None
                raise ToolUnavailable("add_to_calendar: Google rejected token — reconnect in Settings")
            r.raise_for_status()
        except httpx.RequestError as exc:
            raise ToolUnavailable(f"add_to_calendar: network error — {exc}")
        return r.json()

    def _delete(self, path: str) -> None:
        token = self._get_token()
        try:
            with httpx.Client(timeout=15) as client:
                r = client.delete(
                    f"{_CAL_BASE}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if r.status_code == 401:
                self._access_token = None
                raise ToolUnavailable("cancel_event: Google rejected token")
            if r.status_code not in (204, 200, 410):  # 410 = already deleted
                r.raise_for_status()
        except httpx.RequestError as exc:
            raise ToolUnavailable(f"cancel_event: network error — {exc}")

    # ── Public API ───────────────────────────────────────────────────────

    def list_events(self, window_hours: int = 72) -> list[dict]:
        """Events from now → now+window_hours on the primary calendar."""
        now = datetime.now(timezone.utc)
        time_max = (now + timedelta(hours=window_hours)).isoformat()
        data = self._get("/calendars/primary/events", params={
            "timeMin":      now.isoformat(),
            "timeMax":      time_max,
            "singleEvents": "true",
            "orderBy":      "startTime",
            "maxResults":   "50",
        })
        events = []
        for item in data.get("items", []):
            start_raw = item.get("start", {})
            end_raw   = item.get("end", {})
            events.append({
                "id":          item.get("id"),
                "title":       item.get("summary", "(no title)"),
                "start":       start_raw.get("dateTime") or start_raw.get("date"),
                "end":         end_raw.get("dateTime") or end_raw.get("date"),
                "location":    item.get("location"),
                "description": item.get("description", "")[:200],
                "attendees":   [a.get("email") for a in item.get("attendees", [])],
                "status":      item.get("status"),
            })
        return events

    def create_event(self, title: str, start_iso: str, duration_minutes: int = 60,
                     description: str = "", attendees: list[str] | None = None,
                     location: str = "") -> dict:
        """Create an event on the primary calendar. Returns the created event id."""
        from datetime import datetime as _dt
        start_dt = _dt.fromisoformat(start_iso)
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        body: dict = {
            "summary":   title,
            "start":     {"dateTime": start_dt.isoformat()},
            "end":       {"dateTime": end_dt.isoformat()},
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        result = self._post("/calendars/primary/events", body)
        return {"id": result.get("id"), "html_link": result.get("htmlLink")}

    def delete_event(self, event_id: str) -> None:
        self._delete(f"/calendars/primary/events/{event_id}")
