import asyncio
import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from vello.api.deps import create_access_token, get_current_user
from vello.config import ENV
from vello.database import (
    change_password,
    consume_reset_token,
    count_recent_rate_limit_attempts,
    create_password_reset_token,
    create_user,
    get_active_triggers,
    get_connection,
    get_context,
    get_dialogue_history,
    get_routines,
    get_temporal_patterns,
    get_user_by_email,
    get_user_by_id,
    get_valid_reset_token,
    get_zones,
    record_rate_limit_attempt,
    set_verification_token,
    verify_email_token,
    verify_password,
)
from vello.email import send_password_reset_email, send_verification_email

_IS_PROD = ENV == "production"

router = APIRouter()


def _check_rate(bucket: str, key: str, max_attempts: int = 10, window_seconds: int = 300) -> None:
    """DB-backed rate limiter — survives restarts and shared across workers."""
    if count_recent_rate_limit_attempts(bucket, key, window_seconds) >= max_attempts:
        raise HTTPException(status_code=429, detail="too_many_attempts")
    record_rate_limit_attempt(bucket, key)


class AuthBody(BaseModel):
    email: EmailStr
    password: str


class DeleteBody(BaseModel):
    password: str


# ── Auth ───────────────────────────────────────────────────────────────────────

def _send_verification(user_id: str, email: str) -> None:
    """Generate, persist, and email a verification token."""
    token = secrets.token_urlsafe(32)
    set_verification_token(user_id, token)
    send_verification_email(email, token)


@router.post("/register", status_code=201)
async def register(body: AuthBody, request: Request, response: Response):
    _check_rate("reg", request.client.host if request.client else "unknown")
    if get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="email_taken")
    # Reasonable bounds — bcrypt has a 72-char input cap and long inputs make
    # the hash slow enough to be a DOS vector.
    if not (8 <= len(body.password) <= 128):
        raise HTTPException(status_code=422, detail="password_length_invalid")
    # bcrypt hashing in create_user blocks ~100ms; run off the event loop.
    user_id = await asyncio.to_thread(create_user, body.email, body.password)
    _send_verification(user_id, body.email)
    token = create_access_token(user_id)
    response.set_cookie("vello_token", token, httponly=True, samesite="lax",
                        secure=_IS_PROD, max_age=60 * 60 * 24 * 30)
    return {"id": user_id, "email": body.email, "email_verified": False}


@router.post("/login")
async def login(body: AuthBody, request: Request, response: Response):
    _check_rate("login", request.client.host if request.client else "unknown")
    user = get_user_by_email(body.email)
    valid = user is not None and await asyncio.to_thread(verify_password, user, body.password)
    if not valid:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(user["id"])
    response.set_cookie("vello_token", token, httponly=True, samesite="lax",
                        secure=_IS_PROD, max_age=60 * 60 * 24 * 30)
    return {"id": user["id"], "email": user["email"],
            "onboarding_complete": bool(user["onboarding_complete"]),
            "email_verified": bool(user["email_verified"])}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("vello_token")
    return {"ok": True}


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "onboarding_complete": bool(user["onboarding_complete"]),
        "has_kortex": bool(user["kortex_token"]),
        "email_verified": bool(user["email_verified"]),
    }


# ── Account deletion (GDPR Art. 17) ───────────────────────────────────────────

@router.delete("/me")
async def delete_account(body: DeleteBody, response: Response,
                          user=__import__("fastapi").Depends(get_current_user)):
    valid = await asyncio.to_thread(verify_password, user, body.password)
    if not valid:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    conn = get_connection()
    with conn:
        # Cascade FKs handle child tables; explicit waitlist clear since it's email-keyed.
        conn.execute("DELETE FROM waitlist WHERE email=?", (user["email"],))
        conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
    conn.close()
    response.delete_cookie("vello_token")
    return {"ok": True}


# ── Data export (GDPR Art. 20) ────────────────────────────────────────────────

@router.get("/me/export")
def export_account(user=__import__("fastapi").Depends(get_current_user),
                   request: Request = None):
    """GDPR Art. 20 — return everything we hold on this user."""
    if request is not None:
        _check_rate("export", request.client.host if request.client else "unknown",
                    max_attempts=3, window_seconds=3600)
    uid = user["id"]
    conn = get_connection()
    contacts          = [dict(r) for r in conn.execute("SELECT * FROM contacts WHERE user_id=?",          (uid,)).fetchall()]
    inferences        = [dict(r) for r in conn.execute("SELECT * FROM pending_inferences WHERE user_id=?", (uid,)).fetchall()]
    action_log        = [dict(r) for r in conn.execute("SELECT * FROM action_log WHERE user_id=?",         (uid,)).fetchall()]
    location_events   = [dict(r) for r in conn.execute("SELECT * FROM location_events WHERE user_id=?",    (uid,)).fetchall()]
    conn.close()

    return {
        "user": {"email": user["email"], "created_at": user["created_at"]},
        "context":          [dict(r) for r in get_context(uid)],
        "dialogue":         [dict(r) for r in get_dialogue_history(uid, limit=10000)],
        "routines":         [dict(r) for r in get_routines(uid)],
        "zones":            [dict(r) for r in get_zones(uid)],
        "temporal_patterns": [dict(r) for r in get_temporal_patterns(uid)],
        "signals":          [dict(r) for r in get_active_triggers(uid)],
        "contacts":         contacts,
        "pending_inferences": inferences,
        "action_log":       action_log,
        "location_events":  location_events,
    }


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/resend-verification", status_code=204)
def resend_verification(request: Request, user=Depends(get_current_user)):
    if user["email_verified"]:
        raise HTTPException(status_code=400, detail="already_verified")
    _check_rate("verify_resend", user["id"], max_attempts=3, window_seconds=3600)
    _send_verification(user["id"], user["email"])


@router.get("/verify-email")
def verify_email(token: str):
    user = verify_email_token(token)
    if not user:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    return {"ok": True, "email": user["email"], "email_verified": True}


# ── Password reset ────────────────────────────────────────────────────────────

class ForgotPasswordBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    token:        str   = Field(min_length=1, max_length=128)
    new_password: str   = Field(min_length=8, max_length=128)


_RESET_PER_HOUR_PER_IP = 5


@router.post("/forgot-password", status_code=204)
def forgot_password(body: ForgotPasswordBody, request: Request):
    """
    Always returns 204 — never reveals whether the email exists. If a user
    matches, they get a one-hour reset link via Resend.
    """
    ip = request.client.host if request.client else "unknown"
    _check_rate("pwreset_request", ip,
                max_attempts=_RESET_PER_HOUR_PER_IP, window_seconds=3600)
    user = get_user_by_email(body.email)
    if user:
        token = create_password_reset_token(user["id"])
        send_password_reset_email(user["email"], token)


@router.post("/reset-password", status_code=204)
def reset_password(body: ResetPasswordBody, request: Request):
    ip = request.client.host if request.client else "unknown"
    _check_rate("pwreset_consume", ip,
                max_attempts=_RESET_PER_HOUR_PER_IP, window_seconds=3600)
    row = get_valid_reset_token(body.token)
    if not row:
        raise HTTPException(status_code=400, detail="invalid_or_expired_token")
    change_password(row["user_id"], body.new_password)
    consume_reset_token(body.token)
