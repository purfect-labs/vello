"""
Kortex ↔ Vello sync (post-audit rewrite).

- Validates and stores the user's Kortex personal token (encrypted at rest).
- /import pulls the signed export, verifies the signature, then ingests:
    · life_context entries (already domain-mapped server-side)
    · facts with verification_level (low-confidence unverified facts skipped)
    · contradictions converted to pending_inferences
- Token rotation: if Kortex returns 401, the local token is cleared so the
  user is prompted to reconnect rather than seeing a silent loop of failures.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from vello.api.deps import get_current_user
from vello.database import (
    create_inference,
    get_kortex_token,
    set_kortex_token,
    upsert_context,
)
from vello.kortex_client import (
    KortexAuthError,
    KortexSignatureError,
    KortexUnreachable,
    fetch_export,
    validate_token,
)
from vello.signals import fire_signals

router = APIRouter()

# Skip facts below this verification level when computing context confidence
# bumps. Verified facts get a higher local confidence so Vello can weight
# them in retrieval and dialogue.
_VERIFICATION_CONFIDENCE = {
    "source_verified": 0.95,
    "user_attested":   0.90,
    "corroborated":    0.85,
    "unverified":      0.70,
}


class TokenBody(BaseModel):
    token: str


@router.post("/connect")
async def connect_kortex(body: TokenBody, user=Depends(get_current_user)):
    if not body.token.startswith("ktx_"):
        raise HTTPException(status_code=422, detail="invalid_token_format")
    try:
        ok = validate_token(body.token)
    except KortexUnreachable:
        raise HTTPException(status_code=502, detail="kortex_unreachable")
    if not ok:
        raise HTTPException(status_code=401, detail="kortex_token_invalid")
    set_kortex_token(user["id"], body.token)
    return {"ok": True}


@router.post("/import")
async def import_from_kortex(user=Depends(get_current_user)):
    token = get_kortex_token(user["id"])
    if not token:
        raise HTTPException(status_code=400, detail="kortex_not_connected")

    try:
        data = fetch_export(token)
    except KortexAuthError:
        # Token rotated or revoked — clear it so the user is prompted to reconnect
        # rather than seeing a silent loop of 502s on every import.
        set_kortex_token(user["id"], "")
        raise HTTPException(status_code=401, detail="kortex_token_invalid_cleared")
    except KortexSignatureError:
        raise HTTPException(status_code=502, detail="kortex_signature_mismatch")
    except KortexUnreachable:
        raise HTTPException(status_code=502, detail="kortex_unreachable")

    imported_context = 0
    text_parts: list[str] = []

    for entry in data.get("life_context", []):
        upsert_context(
            user["id"],
            domain=entry["domain"],
            key=entry["key"],
            value=entry["value"],
            source="kortex",
            confidence=0.85,
        )
        imported_context += 1
        text_parts.append(entry["value"])

    # Facts: verified facts get a higher local confidence; unverified facts are
    # imported but excluded from signal scanning so unsubstantiated chatter
    # (e.g. "I might quit") doesn't fire job_change watches.
    imported_facts = 0
    for fact in data.get("facts", []):
        level = fact.get("verification_level", "unverified")
        confidence = _VERIFICATION_CONFIDENCE.get(level, 0.7)
        upsert_context(
            user["id"],
            domain=fact["domain"],
            key=fact["key"],
            value=str(fact["value"]),
            source=f"kortex:{level}",
            confidence=confidence,
        )
        imported_facts += 1
        if level != "unverified":
            text_parts.append(str(fact["value"]))

    signals_fired = fire_signals(user["id"], " ".join(text_parts))

    contradictions_imported = 0
    for c in data.get("contradictions", []):
        create_inference(
            user["id"],
            inference_type="contradiction",
            description=(
                f"Contradiction in {c['domain']}.{c['path']}: "
                f"previously '{c['old_value']}', now '{c['new_value']}'. "
                f"Which is current? ({c.get('rationale', 'no context')})"
            ),
            proposed={
                "domain":    c["domain"],
                "path":      c["path"],
                "old_value": c["old_value"],
                "new_value": c["new_value"],
                "kortex_id": c["id"],
            },
        )
        contradictions_imported += 1

    # ── Enriched import: seed household model from Kortex triples + facts ─────
    household_seeded = _seed_household_from_kortex(user["id"], data)

    return {
        "imported_context":         imported_context,
        "imported_facts":           imported_facts,
        "signals_fired":            signals_fired,
        "contradictions_imported":  contradictions_imported,
        "kortex_last_activity_at":  data.get("last_activity_at"),
        "kortex_profile_version":   data.get("profile_version"),
        "email":                    data.get("email"),
        "household_seeded":         household_seeded,
    }


def _seed_household_from_kortex(user_id: str, data: dict) -> dict:
    """
    Walk Kortex triples + facts to seed Vello's household model:
      - Relationship triples → household_members
      - Address triple → households.address (geocode if Google Maps key available)
      - Dietary/allergy facts → member_preferences + grocery list filters

    Returns a summary dict for the API response.
    """
    from vello import database as db

    hh = db.get_or_create_household(user_id)
    hh_id = hh["id"]

    members_upserted = 0
    prefs_upserted = 0

    triples = data.get("triples", []) or []
    facts = data.get("facts", []) or []

    # Predicate → (kind, relationship)
    _RELATIONSHIP_PREDICATES = {
        "lives_with":       ("person", "household"),
        "married_to":       ("person", "partner"),
        "partner_of":       ("person", "partner"),
        "spouse_of":        ("person", "partner"),
        "parent_of":        ("child", "child"),
        "child_of":         ("person", "parent"),
        "has_pet":          ("pet", "pet"),
        "owns_pet":         ("pet", "pet"),
        "has_dog":          ("pet", "dog"),
        "has_cat":          ("pet", "cat"),
        "sibling_of":       ("person", "sibling"),
        "roommate_of":      ("person", "roommate"),
    }

    for triple in triples:
        pred = (triple.get("predicate") or "").lower()
        if pred not in _RELATIONSHIP_PREDICATES:
            continue
        obj = triple.get("object")
        if not obj or not isinstance(obj, str):
            continue
        kind, relationship = _RELATIONSHIP_PREDICATES[pred]
        db.upsert_household_member(
            hh_id, kind=kind, name=obj, relationship=relationship,
        )
        members_upserted += 1

    # Address triple
    for triple in triples:
        pred = (triple.get("predicate") or "").lower()
        if pred in ("lives_at", "home_address", "address"):
            addr = triple.get("object")
            if addr and isinstance(addr, str):
                conn = db.get_connection()
                with conn:
                    conn.execute(
                        "UPDATE households SET address=? WHERE id=? AND address IS NULL",
                        (addr, hh_id),
                    )
                conn.close()
                break

    # Facts: allergies, dietary restrictions → member_preferences
    # We seed these on a synthetic "owner" entity if no specific member found.
    _DIETARY_KEYS = {"allergy", "allergies", "dietary_restriction",
                     "food_preference", "diet", "intolerance"}

    owner_mid: str | None = None

    for fact in facts:
        key = (fact.get("key") or "").lower()
        domain = (fact.get("domain") or "").lower()
        val = str(fact.get("value") or "")
        if not val:
            continue
        if domain in ("health", "preferences") and any(k in key for k in _DIETARY_KEYS):
            # Seed on the owner member (lazy-create a self-member once)
            if owner_mid is None:
                owner_mid = db.upsert_household_member(
                    hh_id, kind="person", name="Me (owner)", relationship="owner",
                )
            db.upsert_member_preference(owner_mid, domain, key, val, source="kortex")
            prefs_upserted += 1

    return {
        "members_upserted": members_upserted,
        "prefs_upserted":   prefs_upserted,
    }


@router.delete("/disconnect")
def disconnect_kortex(user=Depends(get_current_user)):
    set_kortex_token(user["id"], "")
    return {"ok": True}
