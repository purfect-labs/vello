from fastapi import APIRouter, Depends
from vello.api.deps import get_current_user
from vello.gaps import detect_gaps, gaps_as_context

router = APIRouter()


@router.get("/")
def list_gaps(user=Depends(get_current_user)):
    """Behavioral gaps: stated life_context vs. observed temporal patterns."""
    return detect_gaps(user["id"])


@router.get("/context")
def gaps_context(user=Depends(get_current_user)):
    return {"context": gaps_as_context(user["id"])}
