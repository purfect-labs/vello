import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from vello.database import get_connection, now

router = APIRouter()


class WaitlistBody(BaseModel):
    email: EmailStr


@router.post("/waitlist", status_code=201)
def join_waitlist(body: WaitlistBody):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM waitlist WHERE email=?", (body.email.lower().strip(),)
    ).fetchone()
    if existing:
        conn.close()
        return {"ok": True, "already_joined": True}
    try:
        with conn:
            conn.execute(
                "INSERT INTO waitlist (id, email, created_at) VALUES (?,?,?)",
                (str(uuid.uuid4()), body.email.lower().strip(), now()),
            )
    except Exception:
        raise HTTPException(status_code=500, detail="db_error")
    finally:
        conn.close()
    return {"ok": True, "already_joined": False}
