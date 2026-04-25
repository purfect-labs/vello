import sqlite3
import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from vello.config import DB_PATH


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id                  TEXT PRIMARY KEY,
                email               TEXT UNIQUE NOT NULL,
                password_hash       TEXT NOT NULL,
                kortex_token        TEXT,
                onboarding_complete INTEGER NOT NULL DEFAULT 0,
                created_at          TEXT NOT NULL
            );

            -- Flexible life context: domain/key/value triplets
            -- source: manual | conversation | inferred | kortex
            CREATE TABLE IF NOT EXISTS life_context (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                domain      TEXT NOT NULL,
                key         TEXT NOT NULL,
                value       TEXT NOT NULL,
                source      TEXT NOT NULL DEFAULT 'manual',
                confidence  REAL NOT NULL DEFAULT 1.0,
                updated_at  TEXT NOT NULL,
                UNIQUE(user_id, domain, key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Conversational dialogue history
            CREATE TABLE IF NOT EXISTS dialogue (
                id            TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                role          TEXT NOT NULL,
                content       TEXT NOT NULL,
                intent        TEXT,
                created_at    TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Key contacts (partner, family, etc.)
            CREATE TABLE IF NOT EXISTS contacts (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                label           TEXT NOT NULL,
                name            TEXT NOT NULL,
                phone           TEXT,
                notify_mode     TEXT NOT NULL DEFAULT 'confirm',
                created_at      TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Routines: learned or manually defined
            -- schedule_json: {"days": ["mon","wed","fri"], "time": "18:00", "window_minutes": 30}
            CREATE TABLE IF NOT EXISTS routines (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                name            TEXT NOT NULL,
                type            TEXT NOT NULL,
                schedule_json   TEXT NOT NULL DEFAULT '{}',
                active          INTEGER NOT NULL DEFAULT 1,
                confidence      REAL NOT NULL DEFAULT 1.0,
                source          TEXT NOT NULL DEFAULT 'manual',
                created_at      TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Geofence zones
            CREATE TABLE IF NOT EXISTS zones (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                label           TEXT NOT NULL,
                type            TEXT NOT NULL,
                address         TEXT,
                lat             REAL,
                lng             REAL,
                radius_meters   INTEGER NOT NULL DEFAULT 200,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Location events from mobile
            CREATE TABLE IF NOT EXISTS location_events (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                zone_id     TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            );

            -- Inferences awaiting confirmation
            CREATE TABLE IF NOT EXISTS pending_inferences (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                inference_type  TEXT NOT NULL,
                description     TEXT NOT NULL,
                proposed_json   TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT NOT NULL,
                resolved_at     TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Audit log of everything Vello does
            CREATE TABLE IF NOT EXISTS action_log (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                action_type TEXT NOT NULL,
                description TEXT NOT NULL,
                payload_json TEXT,
                status      TEXT NOT NULL DEFAULT 'executed',
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            -- Intent-signal triggers (matched from text scan)
            -- status: pending | confirmed | dismissed
            CREATE TABLE IF NOT EXISTS signal_triggers (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                signal_id       TEXT NOT NULL,
                label           TEXT NOT NULL,
                priority        TEXT NOT NULL,
                action_type     TEXT NOT NULL,
                trigger_message TEXT NOT NULL,
                source_text     TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                expires_at      TEXT NOT NULL,
                created_at      TEXT NOT NULL,
                resolved_at     TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_signal_triggers_user_status
                ON signal_triggers(user_id, status);

            -- Signal watches: downstream signals activated by chaining.
            -- factor=0 bypasses dedup entirely; factor=0.5 halves the dedup window.
            CREATE TABLE IF NOT EXISTS signal_watches (
                id                      TEXT PRIMARY KEY,
                user_id                 TEXT NOT NULL,
                watched_signal_id       TEXT NOT NULL,
                triggered_by_signal_id  TEXT NOT NULL,
                factor                  REAL NOT NULL DEFAULT 0.5,
                expires_at              TEXT NOT NULL,
                created_at              TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_signal_watches_lookup
                ON signal_watches(user_id, watched_signal_id, expires_at);

            -- Temporal observations: raw time-of-day data points
            -- minutes: minutes since midnight (e.g. 7:30am = 450)
            -- day_of_week: 0=Mon … 6=Sun
            CREATE TABLE IF NOT EXISTS temporal_observations (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                pattern_key TEXT NOT NULL,
                minutes     INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                observed_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_temporal_obs_user_key
                ON temporal_observations(user_id, pattern_key);

            -- Temporal pattern summaries (computed from observations)
            CREATE TABLE IF NOT EXISTS temporal_patterns (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL,
                pattern_key     TEXT NOT NULL,
                label           TEXT NOT NULL,
                mean_minutes    REAL,
                std_dev_minutes REAL,
                sample_count    INTEGER NOT NULL DEFAULT 0,
                typical_days    TEXT NOT NULL DEFAULT '[]',
                last_updated    TEXT NOT NULL,
                UNIQUE(user_id, pattern_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)
    conn.close()


# ── Users ──────────────────────────────────────────────────────────────────────

import bcrypt

def create_user(email: str, password: str) -> str:
    uid = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?,?,?,?)",
            (uid, email.lower().strip(), pw_hash, now()),
        )
    conn.close()
    return uid


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    conn.close()
    return row


def get_user_by_id(uid: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row


def verify_password(user: sqlite3.Row, password: str) -> bool:
    return bcrypt.checkpw(password.encode(), user["password_hash"].encode())


def set_kortex_token(user_id: str, token: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute("UPDATE users SET kortex_token=? WHERE id=?", (token, user_id))
    conn.close()


def mark_onboarding_complete(user_id: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute("UPDATE users SET onboarding_complete=1 WHERE id=?", (user_id,))
    conn.close()


# ── Life Context ───────────────────────────────────────────────────────────────

def upsert_context(user_id: str, domain: str, key: str, value: str,
                   source: str = "manual", confidence: float = 1.0) -> None:
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO life_context (id, user_id, domain, key, value, source, confidence, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id, domain, key) DO UPDATE SET
                value=excluded.value, source=excluded.source,
                confidence=excluded.confidence, updated_at=excluded.updated_at
        """, (str(uuid.uuid4()), user_id, domain, key, str(value), source, confidence, now()))
    conn.close()


def get_context(user_id: str, domain: Optional[str] = None) -> list[sqlite3.Row]:
    conn = get_connection()
    if domain:
        rows = conn.execute(
            "SELECT * FROM life_context WHERE user_id=? AND domain=? ORDER BY domain, key",
            (user_id, domain)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM life_context WHERE user_id=? ORDER BY domain, key",
            (user_id,)
        ).fetchall()
    conn.close()
    return rows


def delete_context_entry(user_id: str, domain: str, key: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "DELETE FROM life_context WHERE user_id=? AND domain=? AND key=?",
            (user_id, domain, key)
        )
    conn.close()
    return cur.rowcount > 0


def context_as_text(user_id: str) -> str:
    rows = get_context(user_id)
    if not rows:
        return "No context known yet."
    lines = []
    current_domain = None
    for r in rows:
        if r["domain"] != current_domain:
            current_domain = r["domain"]
            lines.append(f"\n[{current_domain.upper()}]")
        lines.append(f"  {r['key']}: {r['value']}")
    return "\n".join(lines).strip()


# ── Dialogue ───────────────────────────────────────────────────────────────────

def save_dialogue_turn(user_id: str, role: str, content: str, intent: Optional[str] = None) -> str:
    mid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO dialogue (id, user_id, role, content, intent, created_at) VALUES (?,?,?,?,?,?)",
            (mid, user_id, role, content, intent, now())
        )
    conn.close()
    return mid


def get_dialogue_history(user_id: str, limit: int = 30) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM dialogue WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return list(reversed(rows))


# ── Contacts ───────────────────────────────────────────────────────────────────

def create_contact(user_id: str, label: str, name: str,
                   phone: Optional[str], notify_mode: str = "confirm") -> str:
    cid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO contacts (id, user_id, label, name, phone, notify_mode, created_at) VALUES (?,?,?,?,?,?,?)",
            (cid, user_id, label, name, phone, notify_mode, now())
        )
    conn.close()
    return cid


def get_contacts(user_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM contacts WHERE user_id=? ORDER BY label", (user_id,)).fetchall()
    conn.close()
    return rows


def delete_contact(user_id: str, contact_id: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute("DELETE FROM contacts WHERE id=? AND user_id=?", (contact_id, user_id))
    conn.close()
    return cur.rowcount > 0


# ── Routines ───────────────────────────────────────────────────────────────────

def create_routine(user_id: str, name: str, rtype: str,
                   schedule: dict, source: str = "manual") -> str:
    import json
    rid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO routines (id, user_id, name, type, schedule_json, source, created_at) VALUES (?,?,?,?,?,?,?)",
            (rid, user_id, name, rtype, json.dumps(schedule), source, now())
        )
    conn.close()
    return rid


def get_routines(user_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM routines WHERE user_id=? ORDER BY name", (user_id,)).fetchall()
    conn.close()
    return rows


def toggle_routine(user_id: str, routine_id: str, active: bool) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE routines SET active=? WHERE id=? AND user_id=?",
            (1 if active else 0, routine_id, user_id)
        )
    conn.close()
    return cur.rowcount > 0


def delete_routine(user_id: str, routine_id: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute("DELETE FROM routines WHERE id=? AND user_id=?", (routine_id, user_id))
    conn.close()
    return cur.rowcount > 0


# ── Zones ──────────────────────────────────────────────────────────────────────

def create_zone(user_id: str, label: str, ztype: str, address: Optional[str],
                lat: Optional[float], lng: Optional[float], radius: int = 200) -> str:
    zid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO zones (id, user_id, label, type, address, lat, lng, radius_meters, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (zid, user_id, label, ztype, address, lat, lng, radius, now())
        )
    conn.close()
    return zid


def get_zones(user_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM zones WHERE user_id=? ORDER BY type, label", (user_id,)).fetchall()
    conn.close()
    return rows


def delete_zone(user_id: str, zone_id: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute("DELETE FROM zones WHERE id=? AND user_id=?", (zone_id, user_id))
    conn.close()
    return cur.rowcount > 0


# ── Pending Inferences ─────────────────────────────────────────────────────────

def create_inference(user_id: str, inference_type: str, description: str, proposed: dict) -> str:
    import json
    iid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO pending_inferences (id, user_id, inference_type, description, proposed_json, created_at) VALUES (?,?,?,?,?,?)",
            (iid, user_id, inference_type, description, json.dumps(proposed), now())
        )
    conn.close()
    return iid


def get_pending_inferences(user_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM pending_inferences WHERE user_id=? AND status='pending' ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def resolve_inference(user_id: str, inference_id: str, status: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM pending_inferences WHERE id=? AND user_id=?",
        (inference_id, user_id)
    ).fetchone()
    if row:
        with conn:
            conn.execute(
                "UPDATE pending_inferences SET status=?, resolved_at=? WHERE id=?",
                (status, now(), inference_id)
            )
    conn.close()
    return row


# ── Action Log ─────────────────────────────────────────────────────────────────

def log_action(user_id: str, action_type: str, description: str,
               payload: Optional[dict] = None, status: str = "executed") -> str:
    import json
    aid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO action_log (id, user_id, action_type, description, payload_json, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (aid, user_id, action_type, description,
             json.dumps(payload) if payload else None, status, now())
        )
    conn.close()
    return aid


def get_action_log(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM action_log WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return rows


# ── Signal Triggers ────────────────────────────────────────────────────────────

def has_active_trigger(user_id: str, signal_id: str) -> bool:
    """Return True if an unexpired pending trigger already exists for this signal."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM signal_triggers WHERE user_id=? AND signal_id=? AND status='pending' AND expires_at > ?",
        (user_id, signal_id, now())
    ).fetchone()
    conn.close()
    return row is not None


def create_signal_trigger(user_id: str, signal_id: str, label: str, priority: str,
                           action_type: str, trigger_message: str,
                           source_text: Optional[str], decay_hours: int) -> str:
    from datetime import timedelta
    tid = str(uuid.uuid4())
    expires = (datetime.now(timezone.utc) + timedelta(hours=decay_hours)).isoformat()
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO signal_triggers
               (id, user_id, signal_id, label, priority, action_type, trigger_message,
                source_text, expires_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (tid, user_id, signal_id, label, priority, action_type, trigger_message,
             source_text, expires, now())
        )
    conn.close()
    return tid


def get_active_triggers(user_id: str) -> list[sqlite3.Row]:
    """Return all pending, non-expired triggers ordered by priority then time."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM signal_triggers
           WHERE user_id=? AND status='pending' AND expires_at > ?
           ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at DESC""",
        (user_id, now())
    ).fetchall()
    conn.close()
    return rows


def get_active_watch(user_id: str, signal_id: str) -> Optional[sqlite3.Row]:
    """Return the most-permissive (lowest factor) active watch for a signal, if any."""
    conn = get_connection()
    row = conn.execute(
        """SELECT * FROM signal_watches
           WHERE user_id=? AND watched_signal_id=? AND expires_at > ?
           ORDER BY factor ASC LIMIT 1""",
        (user_id, signal_id, now())
    ).fetchone()
    conn.close()
    return row


def create_signal_watch(user_id: str, watched_signal_id: str,
                        triggered_by: str, factor: float, watch_hours: int) -> str:
    from datetime import timedelta
    wid = str(uuid.uuid4())
    expires = (datetime.now(timezone.utc) + timedelta(hours=watch_hours)).isoformat()
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT OR REPLACE INTO signal_watches
               (id, user_id, watched_signal_id, triggered_by_signal_id, factor, expires_at, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (wid, user_id, watched_signal_id, triggered_by, factor, expires, now())
        )
    conn.close()
    return wid


def resolve_signal_trigger(user_id: str, trigger_id: str, status: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE signal_triggers SET status=?, resolved_at=? WHERE id=? AND user_id=?",
            (status, now(), trigger_id, user_id)
        )
    conn.close()
    return cur.rowcount > 0


# ── Temporal Patterns ──────────────────────────────────────────────────────────

def log_temporal_observation(user_id: str, pattern_key: str,
                              minutes: int, day_of_week: int) -> str:
    oid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO temporal_observations (id, user_id, pattern_key, minutes, day_of_week, observed_at) VALUES (?,?,?,?,?,?)",
            (oid, user_id, pattern_key, minutes, day_of_week, now())
        )
    conn.close()
    return oid


def get_temporal_observations(user_id: str, pattern_key: str,
                               limit: int = 90) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM temporal_observations WHERE user_id=? AND pattern_key=? ORDER BY observed_at DESC LIMIT ?",
        (user_id, pattern_key, limit)
    ).fetchall()
    conn.close()
    return rows


def upsert_temporal_pattern(user_id: str, pattern_key: str, label: str,
                             mean_minutes: float, std_dev_minutes: float,
                             sample_count: int, typical_days: list[int]) -> None:
    import json
    conn = get_connection()
    with conn:
        conn.execute(
            """INSERT INTO temporal_patterns
               (id, user_id, pattern_key, label, mean_minutes, std_dev_minutes,
                sample_count, typical_days, last_updated)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id, pattern_key) DO UPDATE SET
                   label=excluded.label, mean_minutes=excluded.mean_minutes,
                   std_dev_minutes=excluded.std_dev_minutes, sample_count=excluded.sample_count,
                   typical_days=excluded.typical_days, last_updated=excluded.last_updated""",
            (str(uuid.uuid4()), user_id, pattern_key, label,
             mean_minutes, std_dev_minutes, sample_count,
             json.dumps(sorted(set(typical_days))), now())
        )
    conn.close()


def get_temporal_patterns(user_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM temporal_patterns WHERE user_id=? ORDER BY pattern_key",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_temporal_pattern(user_id: str, pattern_key: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM temporal_patterns WHERE user_id=? AND pattern_key=?",
        (user_id, pattern_key)
    ).fetchone()
    conn.close()
    return row
