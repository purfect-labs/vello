from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, EmailStr

from vello.api.deps import create_access_token
from vello.database import create_user, get_user_by_email, verify_password

router = APIRouter()


class AuthBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=201)
def register(body: AuthBody, response: Response):
    if get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="email_taken")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="password_too_short")
    user_id = create_user(body.email, body.password)
    token = create_access_token(user_id)
    response.set_cookie("vello_token", token, httponly=True, samesite="lax",
                        secure=False, max_age=60 * 60 * 24 * 30)
    return {"id": user_id, "email": body.email}


@router.post("/login")
def login(body: AuthBody, response: Response):
    user = get_user_by_email(body.email)
    if not user or not verify_password(user, body.password):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_access_token(user["id"])
    response.set_cookie("vello_token", token, httponly=True, samesite="lax",
                        secure=False, max_age=60 * 60 * 24 * 30)
    return {"id": user["id"], "email": user["email"],
            "onboarding_complete": bool(user["onboarding_complete"])}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("vello_token")
    return {"ok": True}


@router.get("/me")
def me(user=__import__("fastapi").Depends(__import__("vello.api.deps", fromlist=["get_current_user"]).get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "onboarding_complete": bool(user["onboarding_complete"]),
        "has_kortex": bool(user["kortex_token"]),
    }
