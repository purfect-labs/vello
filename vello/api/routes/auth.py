import time
from collections import defaultdict

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from vello.api.deps import create_access_token, get_current_user
from vello.database import (
    create_user, get_user_by_email, verify_password, get_user_by_id,
    get_context, get_dialogue_history, get_routines, get_zones,
    get_temporal_patterns, get_active_triggers, get_connection,
)

router = APIRouter()

# ── Simple in-memory rate limiter (per IP, resets after window) ────────────────
_attempts: dict[str, list[float]] = defaultdict(list)

def _check_rate(key: str, max_attempts: int = 10, window: int = 300) -> None:
    now = time.time()
    _attempts[key] = [t for t in _attempts[key] if now - t < window]
    if len(_attempts[key]) >= max_attempts:
        raise HTTPException(status_code=429, detail="too_many_attempts")
    _attempts[key].append(now)


class AuthBody(BaseModel):
    email: EmailStr
    password: str


class DeleteBody(BaseModel):
    password: str


# ── Auth ───────────────────────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(body: AuthBody, request: Request, response: Response):
    _check_rate(f"reg:{request.client.host}")
    if get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="email_taken")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="password_too_short")
    user_id = create_user(body.email, body.password)
    token = create_access_token(user_id)
    response.set_cookie("vello_token", token, httponly=True, samesite="lax",
                        secure=True, max_age=60 * 60 * 24 * 30)
    return {"id": user_id, "email": body.email}


@router.post("/login")
def login(body: AuthBody, request: Request, response: Response):
    _check_rate(f"login:{request.client.host}")
    user = get_user_by_email(body.email)
    if not user or not verify_password(user, body.password):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(user["id"])
    response.set_cookie("vello_token", token, httponly=True, samesite="lax",
                        secure=True, max_age=60 * 60 * 24 * 30)
    return {"id": user["id"], "email": user["email"],
            "onboarding_complete": bool(user["onboarding_complete"])}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("vello_token")
    return {"ok": True}


@router.get("/me")
def me(user=__import__("fastapi").Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "onboarding_complete": bool(user["onboarding_complete"]),
        "has_kortex": bool(user["kortex_token"]),
    }


# ── Account deletion (GDPR Art. 17) ───────────────────────────────────────────

@router.delete("/me")
def delete_account(body: DeleteBody, response: Response,
                   user=__import__("fastapi").Depends(get_current_user)):
    if not verify_password(user, body.password):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM users WHERE id=?", (user["id"],))
    conn.close()
    response.delete_cookie("vello_token")
    return {"ok": True}


# ── Data export (GDPR Art. 20) ────────────────────────────────────────────────

@router.get("/me/export")
def export_account(user=__import__("fastapi").Depends(get_current_user)):
    uid = user["id"]
    context   = [dict(r) for r in get_context(uid)]
    dialogue  = [dict(r) for r in get_dialogue_history(uid, limit=10000)]
    routines  = [dict(r) for r in get_routines(uid)]
    zones     = [dict(r) for r in get_zones(uid)]
    patterns  = [dict(r) for r in get_temporal_patterns(uid)]
    signals   = [dict(r) for r in get_active_triggers(uid)]
    return {
        "user": {"email": user["email"], "created_at": user["created_at"]},
        "context":          context,
        "dialogue":         dialogue,
        "routines":         routines,
        "zones":            zones,
        "temporal_patterns": patterns,
        "signals":          signals,
    }
