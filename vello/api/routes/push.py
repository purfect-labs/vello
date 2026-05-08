"""Web push subscription management."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello import database as db
from vello.config import VAPID_PUBLIC_KEY

router = APIRouter()


class SubscribeBody(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: Optional[str] = None


@router.get("/vapid-public-key")
def get_vapid_key():
    """The VAPID public key the frontend uses when creating a push subscription."""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="push_not_configured")
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=201)
def subscribe(body: SubscribeBody, user=Depends(get_current_user)):
    """Store a push subscription endpoint for this user."""
    import uuid
    sub_id = str(uuid.uuid4())
    from vello.database import now
    conn = db.get_connection()
    with conn:
        conn.execute(
            "INSERT INTO push_subscriptions (id, user_id, endpoint, p256dh, auth, "
            "user_agent, created_at) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(endpoint) DO UPDATE SET "
            "user_id=excluded.user_id, p256dh=excluded.p256dh, "
            "auth=excluded.auth, user_agent=excluded.user_agent",
            (sub_id, user["id"], body.endpoint, body.p256dh, body.auth,
             body.user_agent, now()),
        )
    conn.close()
    return {"ok": True}


@router.delete("/subscribe", status_code=204)
def unsubscribe(endpoint: str, user=Depends(get_current_user)):
    """Remove a push subscription."""
    conn = db.get_connection()
    with conn:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE user_id=? AND endpoint=?",
            (user["id"], endpoint),
        )
    conn.close()


@router.post("/test")
def test_push(user=Depends(get_current_user)):
    """Send a test push to the user's subscriptions."""
    from vello.push import send_to_user
    sent = send_to_user(user["id"], "Vello", "Push notifications are working.")
    return {"sent": sent}
