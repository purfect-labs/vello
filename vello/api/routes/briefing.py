from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from vello.api.deps import get_current_user
from vello.database import get_connection

router = APIRouter()


class BriefingPrefs(BaseModel):
    enabled: bool | None = None
    hour: int | None = None  # 0-23 UTC


@router.get("/preferences")
def get_preferences(user=Depends(get_current_user)):
    return {
        "enabled": bool(user["briefing_enabled"]),
        "hour":    user["briefing_hour"],
    }


@router.patch("/preferences")
def update_preferences(body: BriefingPrefs, user=Depends(get_current_user)):
    if body.hour is not None and not (0 <= body.hour <= 23):
        raise HTTPException(status_code=422, detail="hour_out_of_range")

    sets, vals = [], []
    if body.enabled is not None:
        sets.append("briefing_enabled=?")
        vals.append(1 if body.enabled else 0)
    if body.hour is not None:
        sets.append("briefing_hour=?")
        vals.append(body.hour)

    if sets:
        vals.append(user["id"])
        conn = get_connection()
        with conn:
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", vals)
        conn.close()

    return {"ok": True}


@router.post("/send-test")
def send_test(background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    from vello.briefing import send_briefing
    background_tasks.add_task(send_briefing, user["id"], user["email"])
    return {"ok": True, "queued": True}
