"""
Meta-learning hypothesis layer for Vello.

Observes patterns across the user's life context entries and dialogue,
proposes candidate hypotheses, then scores each new observation against
open hypotheses using Bayesian beta-binomial confidence updates.

Ported from Kortex's hypothesis layer with adaptations for Vello's
flatter data model (life_context domain/key/value triplets vs Kortex's
hierarchical profile JSON).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from vello.config import DIALOGUE_MODEL
from vello.database import get_connection
from vello.llm import complete

_logger = logging.getLogger(__name__)

# ── Tunables ──────────────────────────────────────────────────────────────────

_PRIOR_ALPHA = 2.0
_PRIOR_BETA  = 2.0

_PROMOTE_CONFIDENCE  = 0.70
_PROMOTE_MIN_SESSIONS = 2
_PROMOTE_MIN_EVIDENCE = 3

_RETIRE_CONFIDENCE       = 0.30
_RETIRE_MIN_CONTRADICTIONS = 3

_MAX_OPEN_HYPOTHESES = 25
PROPOSE_FREQUENCY    = 8   # every Nth extraction cycle

# ── Bayesian helpers ──────────────────────────────────────────────────────────

def _confidence(evidence: int, contradiction: int) -> float:
    return (_PRIOR_ALPHA + evidence) / (_PRIOR_ALPHA + _PRIOR_BETA + evidence + contradiction)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# ── Schema (added via migration in database.py) ───────────────────────────────
# CREATE TABLE IF NOT EXISTS hypotheses (
#   id TEXT PRIMARY KEY, user_id TEXT NOT NULL, hypothesis_type TEXT NOT NULL,
#   description TEXT NOT NULL, domain_hint TEXT, evidence_count INTEGER DEFAULT 0,
#   contradiction_count INTEGER DEFAULT 0, session_count INTEGER DEFAULT 0,
#   confidence REAL DEFAULT 0.0, last_evidence_at TEXT, status TEXT DEFAULT 'candidate',
#   user_attested INTEGER DEFAULT 0, created_at TEXT NOT NULL,
#   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
# );

# ── DB helpers ─────────────────────────────────────────────────────────────────

def create_candidate(user_id: str, hypothesis_type: str, description: str,
                     domain_hint: Optional[str] = None) -> str:
    hid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO hypotheses (id, user_id, hypothesis_type, description,
               domain_hint, confidence, status, created_at) VALUES (?,?,?,?,?,?,?,?)""",
            (hid, user_id, hypothesis_type, description, domain_hint,
             _confidence(0, 0), "candidate", _now()),
        )
    conn.close()
    return hid


def list_open(user_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM hypotheses WHERE user_id=? AND status != 'retired'
           ORDER BY confidence DESC, created_at ASC""",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_active(user_id: str, min_confidence: float = _PROMOTE_CONFIDENCE) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM hypotheses
           WHERE user_id=? AND status='active'
             AND (confidence >= ? OR user_attested = 1)
           ORDER BY user_attested DESC, confidence DESC""",
        (user_id, min_confidence),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def attest(user_id: str, hypothesis_id: str, attested: bool) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            """UPDATE hypotheses
               SET user_attested = ?, status = CASE WHEN ?=1 THEN 'active' ELSE status END
               WHERE id=? AND user_id=?""",
            (1 if attested else 0, 1 if attested else 0, hypothesis_id, user_id),
        )
    conn.close()
    return cur.rowcount > 0


def retire(user_id: str, hypothesis_id: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE hypotheses SET status='retired' WHERE id=? AND user_id=?",
            (hypothesis_id, user_id),
        )
    conn.close()
    return cur.rowcount > 0


def _evict_to_capacity(user_id: str) -> None:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM hypotheses WHERE user_id=? AND status != 'retired'",
        (user_id,),
    ).fetchone()[0]
    if count <= _MAX_OPEN_HYPOTHESES:
        conn.close()
        return
    with conn:
        conn.execute(
            """UPDATE hypotheses SET status='retired'
               WHERE id IN (
                 SELECT id FROM hypotheses
                 WHERE user_id=? AND status='candidate' AND user_attested=0
                 ORDER BY confidence ASC, created_at ASC LIMIT ?
               )""",
            (user_id, count - _MAX_OPEN_HYPOTHESES),
        )
    conn.close()


def _apply_verdict(hypothesis_id: str, verdict: str, session_id: str,
                   already_seen: set[str]) -> None:
    if verdict not in ("support", "contradict"):
        return
    conn = get_connection()
    row = conn.execute("SELECT * FROM hypotheses WHERE id=?", (hypothesis_id,)).fetchone()
    if not row:
        conn.close()
        return
    new_session = hypothesis_id not in already_seen
    evidence     = row["evidence_count"] + (1 if verdict == "support" else 0)
    contradiction = row["contradiction_count"] + (1 if verdict == "contradict" else 0)
    sessions     = row["session_count"] + (1 if new_session else 0)
    conf         = _confidence(evidence, contradiction)
    new_status   = row["status"]
    if new_status == "candidate":
        if conf >= _PROMOTE_CONFIDENCE and evidence >= _PROMOTE_MIN_EVIDENCE and sessions >= _PROMOTE_MIN_SESSIONS:
            new_status = "active"
    elif new_status == "active":
        if conf < _RETIRE_CONFIDENCE and contradiction >= _RETIRE_MIN_CONTRADICTIONS and not row["user_attested"]:
            new_status = "retired"
    with conn:
        conn.execute(
            """UPDATE hypotheses SET evidence_count=?, contradiction_count=?,
               session_count=?, confidence=?, last_evidence_at=?, status=? WHERE id=?""",
            (evidence, contradiction, sessions, round(conf, 4), _now(), new_status, hypothesis_id),
        )
    conn.close()
    already_seen.add(hypothesis_id)

# ── LLM prompts ───────────────────────────────────────────────────────────────

_PROPOSE_SYSTEM = """\
You are a pattern-finder for a personal life-agent. Given the user's recent
life context and existing hypotheses, propose NEW candidate observations.
Output ONLY valid JSON:

{
  "proposals": [
    {
      "hypothesis_type": "trait | causal | temporal | co_activation | preference | habit | decision_pattern | other",
      "description": "<one-sentence falsifiable statement about this person>",
      "domain_hint": "<schedule|fitness|work|people|home|finance|health|preferences or null>"
    }
  ]
}

Guidelines:
- Each description must be testable against future observations.
- Aim for DIVERSITY: causal ("when stressed, skips workouts"), temporal
  ("exercises only on weekday mornings"), co_activation ("mentions partner
  when discussing finances"). Traits are fine but should not dominate.
- Be concrete: "wakes before 7am on weekdays" not "early riser".
- Prefer 2-4 proposals; skip with proposals=[] when evidence is thin.
- Avoid restating existing hypotheses.
"""

_SCORE_SYSTEM = """\
Score how a new observation bears on the hypotheses listed. Output ONLY valid JSON:

{
  "verdicts": [
    {"id": "<id>", "verdict": "support|contradict|neutral"}
  ]
}

Default to "neutral" when in doubt — false support inflates confidence.
"""

# ── LLM calls ────────────────────────────────────────────────────────────────

def _parse(raw: str) -> dict:
    cleaned = re.sub(r"^```[a-z]*\n?", "", raw.strip())
    cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def propose_for_user(user_id: str) -> int:
    """Propose new candidate hypotheses from recent life context. Returns count created."""
    _evict_to_capacity(user_id)
    open_h = list_open(user_id)
    if len(open_h) >= _MAX_OPEN_HYPOTHESES:
        return 0

    conn = get_connection()
    ctx_rows = conn.execute(
        "SELECT domain, key, value FROM life_context WHERE user_id=? ORDER BY updated_at DESC LIMIT 60",
        (user_id,),
    ).fetchall()
    conn.close()

    if len(ctx_rows) < 5:
        return 0  # not enough signal yet

    facts_blob = "\n".join(f"- [{r['domain']}] {r['key']}: {r['value']}" for r in ctx_rows)
    existing = "\n".join(f"- [{h['hypothesis_type']}] {h['description']}" for h in open_h) or "(none)"

    user_msg = f"<life_context>\n{facts_blob}\n</life_context>\n\n<existing_hypotheses>\n{existing}\n</existing_hypotheses>"

    try:
        raw = complete(_PROPOSE_SYSTEM, [{"role": "user", "content": user_msg}],
                       model=DIALOGUE_MODEL, max_tokens=500)
    except Exception as exc:
        _logger.warning("hypothesis propose failed for user %s: %s", user_id, exc)
        return 0

    proposals = _parse(raw).get("proposals") or []
    created = 0
    for p in proposals:
        if not isinstance(p, dict):
            continue
        desc = (p.get("description") or "").strip()[:500]
        if not desc:
            continue
        create_candidate(user_id, (p.get("hypothesis_type") or "other").strip()[:32],
                         desc, p.get("domain_hint") or None)
        created += 1
    return created


def score_against(user_id: str, observation_text: str, session_id: str) -> int:
    """Score an observation against open hypotheses. Returns count of verdicts applied."""
    open_h = list_open(user_id)
    if not open_h or not observation_text.strip():
        return 0

    h_blob = "\n".join(f"- id={h['id']} [{h['hypothesis_type']}] {h['description']}" for h in open_h)
    user_msg = f"<hypotheses>\n{h_blob}\n</hypotheses>\n\n<observation>\n{observation_text[:2000]}\n</observation>"

    try:
        raw = complete(_SCORE_SYSTEM, [{"role": "user", "content": user_msg}],
                       model=DIALOGUE_MODEL, max_tokens=500)
    except Exception as exc:
        _logger.warning("hypothesis score failed for user %s: %s", user_id, exc)
        return 0

    verdicts = _parse(raw).get("verdicts") or []
    seen: set[str] = set()
    valid_ids = {h["id"] for h in open_h}
    applied = 0
    for v in verdicts:
        if not isinstance(v, dict):
            continue
        hid = v.get("id")
        verdict = v.get("verdict")
        if hid in valid_ids and verdict in ("support", "contradict"):
            _apply_verdict(hid, verdict, session_id, seen)
            applied += 1
    return applied


def hypotheses_as_context(user_id: str, limit: int = 6) -> str:
    """Render active hypotheses for chat context injection."""
    rows = list_active(user_id)
    if not rows:
        return ""
    lines = ["[INFERRED PATTERNS — observed from your behaviour]"]
    for h in rows[:limit]:
        attested = "✓" if h["user_attested"] else " "
        lines.append(f"  {attested} [{h['hypothesis_type']}, {h['confidence']:.0%}] {h['description']}")
    return "\n".join(lines)
