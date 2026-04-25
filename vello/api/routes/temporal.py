"""
Temporal pattern endpoints.

Clients log observations (when the user did X) and query learned patterns.
The mobile app drives this — when a zone exit/enter event fires, it calls
POST /temporal/observe with the pattern key (e.g. "leave_home_morning").
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from vello.api.deps import get_current_user
from vello.temporal import log_observation, predict_pattern, detect_deviations, update_pattern_stats
from vello.database import get_temporal_patterns

router = APIRouter()


class ObserveBody(BaseModel):
    pattern_key: str
    label: str
    minutes: Optional[int] = None  # minutes since midnight; None = use server time


@router.post("/observe")
def observe(body: ObserveBody, user=Depends(get_current_user)):
    """Log one observation of a temporal pattern."""
    result = log_observation(user["id"], body.pattern_key, body.label, body.minutes)
    return result


@router.get("/patterns")
def list_patterns(user=Depends(get_current_user)):
    rows = get_temporal_patterns(user["id"])
    import json
    return [
        {
            "pattern_key":     r["pattern_key"],
            "label":           r["label"],
            "mean_minutes":    r["mean_minutes"],
            "std_dev_minutes": r["std_dev_minutes"],
            "sample_count":    r["sample_count"],
            "typical_days":    json.loads(r["typical_days"]),
            "last_updated":    r["last_updated"],
        }
        for r in rows
    ]


@router.get("/predict/{pattern_key}")
def predict(pattern_key: str, user=Depends(get_current_user)):
    result = predict_pattern(user["id"], pattern_key)
    if result is None:
        raise HTTPException(status_code=404, detail="insufficient_data")
    return result


@router.get("/deviations")
def deviations(user=Depends(get_current_user)):
    """Return patterns where the user is currently running late."""
    return detect_deviations(user["id"])
