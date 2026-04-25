import json
from fastapi import APIRouter, Depends, HTTPException

from vello.api.deps import get_current_user
from vello.database import (
    get_pending_inferences, resolve_inference, upsert_context
)

router = APIRouter()


@router.get("/")
def list_inferences(user=Depends(get_current_user)):
    rows = get_pending_inferences(user["id"])
    result = []
    for r in rows:
        d = dict(r)
        d["proposed"] = json.loads(r["proposed_json"])
        del d["proposed_json"]
        result.append(d)
    return result


@router.post("/{inference_id}/confirm")
def confirm(inference_id: str, user=Depends(get_current_user)):
    row = resolve_inference(user["id"], inference_id, "confirmed")
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    proposed = json.loads(row["proposed_json"])
    for item in proposed.get("entries", []):
        upsert_context(user["id"], item["domain"], item["key"], item["value"],
                       source="inferred", confidence=item.get("confidence", 0.9))
    return {"ok": True}


@router.post("/{inference_id}/dismiss")
def dismiss(inference_id: str, user=Depends(get_current_user)):
    row = resolve_inference(user["id"], inference_id, "dismissed")
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return {"ok": True}
