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
        # Waitlist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS waitlist (
                id         TEXT PRIMARY KEY,
                email      TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Scheduler advisory locks — used for leader election across workers.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_locks (
                job_id      TEXT NOT NULL,
                period_key  TEXT NOT NULL,
                holder      TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                PRIMARY KEY (job_id, period_key)
            )
        """)

        # Persistent rate-limit attempts (replaces in-memory dict that didn't
        # survive restarts and didn't share across workers).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_attempts (
                id         TEXT PRIMARY KEY,
                bucket     TEXT NOT NULL,
                key        TEXT NOT NULL,
                attempt_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rate_limit_lookup "
            "ON rate_limit_attempts(bucket, key, attempt_at)"
        )

        # Schema versioning so migrations are observable rather than silently
        # ignored on AlreadyExists errors.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_versions (
                version    INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)

    _apply_schema_migrations(conn)
    conn.close()


def _apply_schema_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending schema migrations. Failures here are surfaced — silent
    swallowing is what hid bugs in the previous implementation."""
    import logging
    log = logging.getLogger(__name__)

    applied = {r[0] for r in conn.execute("SELECT version FROM schema_versions").fetchall()}

    def _stamp(version: int) -> None:
        conn.execute(
            "INSERT INTO schema_versions (version, applied_at) VALUES (?, ?)",
            (version, now()),
        )
        conn.commit()

    def _add_column_if_missing(table: str, column: str, definition: str) -> None:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column in cols:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.commit()

    # v1: briefing prefs + webhook token
    if 1 not in applied:
        try:
            _add_column_if_missing("users", "briefing_enabled", "INTEGER NOT NULL DEFAULT 1")
            _add_column_if_missing("users", "briefing_hour",    "INTEGER NOT NULL DEFAULT 7")
            _add_column_if_missing("users", "webhook_token",    "TEXT")
            _stamp(1)
        except Exception as exc:
            log.error("schema migration v1 failed: %s", exc)
            raise

    # v2: timezone field on users (used by temporal pattern engine to convert
    # observations into the user's local time-of-day)
    if 2 not in applied:
        try:
            _add_column_if_missing("users", "timezone", "TEXT NOT NULL DEFAULT 'UTC'")
            _stamp(2)
        except Exception as exc:
            log.error("schema migration v2 failed: %s", exc)
            raise

    # v3: email verification + password reset tokens
    if 3 not in applied:
        try:
            _add_column_if_missing("users", "email_verified",       "INTEGER NOT NULL DEFAULT 0")
            _add_column_if_missing("users", "verification_token",   "TEXT")
            _add_column_if_missing("users", "verification_sent_at", "TEXT")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    token      TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used       INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_password_reset_user
                    ON password_reset_tokens(user_id);
            """)
            _stamp(3)
        except Exception as exc:
            log.error("schema migration v3 failed: %s", exc)
            raise

    # v4: hypotheses meta-learning table
    if 4 not in applied:
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS hypotheses (
                    id                  TEXT PRIMARY KEY,
                    user_id             TEXT NOT NULL,
                    hypothesis_type     TEXT NOT NULL,
                    description         TEXT NOT NULL,
                    domain_hint         TEXT,
                    evidence_count      INTEGER NOT NULL DEFAULT 0,
                    contradiction_count INTEGER NOT NULL DEFAULT 0,
                    session_count       INTEGER NOT NULL DEFAULT 0,
                    confidence          REAL NOT NULL DEFAULT 0.0,
                    last_evidence_at    TEXT,
                    status              TEXT NOT NULL DEFAULT 'candidate',
                    user_attested       INTEGER NOT NULL DEFAULT 0,
                    created_at          TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_hypotheses_user_status
                    ON hypotheses(user_id, status, confidence DESC);
            """)
            _stamp(4)
        except Exception as exc:
            log.error("schema migration v4 failed: %s", exc)
            raise

    # v5: home-agent skeleton — household primitives, world model, agent
    # sessions / drafts / campaigns / playbooks / trust stats / oauth.
    # household_id is reserved on every new table so partner-sync (multi-user
    # shared household) becomes a permissions change later, not a migration.
    if 5 not in applied:
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS households (
                    id              TEXT PRIMARY KEY,
                    owner_user_id   TEXT NOT NULL,
                    name            TEXT,
                    address         TEXT,
                    lat             REAL,
                    lng             REAL,
                    timezone        TEXT NOT NULL DEFAULT 'UTC',
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_households_owner
                    ON households(owner_user_id);

                -- kind ∈ {person, child, pet}
                -- channels_json: {"sms": "+1...", "email": "x@y.com", "none": false}
                -- consent_json:  {"model": true, "notify": false}
                CREATE TABLE IF NOT EXISTS household_members (
                    id              TEXT PRIMARY KEY,
                    household_id    TEXT NOT NULL,
                    kind            TEXT NOT NULL DEFAULT 'person',
                    name            TEXT NOT NULL,
                    relationship    TEXT,
                    dob             TEXT,
                    notes           TEXT,
                    channels_json   TEXT NOT NULL DEFAULT '{}',
                    consent_json    TEXT NOT NULL DEFAULT '{"model":true,"notify":false}',
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_household_members_household
                    ON household_members(household_id);

                -- per-member preferences distinct from owner's life_context
                CREATE TABLE IF NOT EXISTS member_preferences (
                    id          TEXT PRIMARY KEY,
                    member_id   TEXT NOT NULL,
                    domain      TEXT NOT NULL,
                    key         TEXT NOT NULL,
                    value       TEXT NOT NULL,
                    source      TEXT NOT NULL DEFAULT 'manual',
                    created_at  TEXT NOT NULL,
                    UNIQUE(member_id, domain, key),
                    FOREIGN KEY (member_id) REFERENCES household_members(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS vendors (
                    id                  TEXT PRIMARY KEY,
                    household_id        TEXT NOT NULL,
                    name                TEXT NOT NULL,
                    kind                TEXT NOT NULL DEFAULT 'custom',
                    phone               TEXT,
                    email               TEXT,
                    last_contacted_at   TEXT,
                    track_record_json   TEXT NOT NULL DEFAULT '{}',
                    source              TEXT NOT NULL DEFAULT 'manual',
                    created_at          TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_vendors_household
                    ON vendors(household_id);

                -- kind ∈ {grocery, hardware, pharmacy, weekly_errands, custom}
                CREATE TABLE IF NOT EXISTS home_lists (
                    id              TEXT PRIMARY KEY,
                    household_id    TEXT NOT NULL,
                    slug            TEXT NOT NULL,
                    label           TEXT NOT NULL,
                    kind            TEXT NOT NULL DEFAULT 'custom',
                    created_at      TEXT NOT NULL,
                    UNIQUE(household_id, slug),
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );

                -- status ∈ {open, done, dropped}; source ∈ {user, agent, kortex}
                CREATE TABLE IF NOT EXISTS home_list_items (
                    id              TEXT PRIMARY KEY,
                    list_id         TEXT NOT NULL,
                    label           TEXT NOT NULL,
                    qty             TEXT,
                    status          TEXT NOT NULL DEFAULT 'open',
                    source          TEXT NOT NULL DEFAULT 'user',
                    created_at      TEXT NOT NULL,
                    completed_at    TEXT,
                    FOREIGN KEY (list_id) REFERENCES home_lists(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_home_list_items_list_status
                    ON home_list_items(list_id, status);

                CREATE TABLE IF NOT EXISTS inventory_items (
                    id                  TEXT PRIMARY KEY,
                    household_id        TEXT NOT NULL,
                    label               TEXT NOT NULL,
                    location_entity_id  TEXT,
                    last_used_at        TEXT,
                    est_lifetime_days   INTEGER,
                    low_threshold_days  INTEGER,
                    restock_url         TEXT,
                    source              TEXT NOT NULL DEFAULT 'user',
                    created_at          TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_inventory_household
                    ON inventory_items(household_id);

                -- kind ∈ {service, delivery, school, pickup, chore, custom}
                CREATE TABLE IF NOT EXISTS home_events (
                    id                  TEXT PRIMARY KEY,
                    household_id        TEXT NOT NULL,
                    title               TEXT NOT NULL,
                    when_at             TEXT NOT NULL,
                    kind                TEXT NOT NULL DEFAULT 'custom',
                    recurrence_json     TEXT NOT NULL DEFAULT '{}',
                    vendor_id           TEXT,
                    member_id           TEXT,
                    source              TEXT NOT NULL DEFAULT 'user',
                    created_at          TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_home_events_household_when
                    ON home_events(household_id, when_at);

                -- kind ∈ {room, object, member, vendor, recurring_event}
                CREATE TABLE IF NOT EXISTS home_entities (
                    id              TEXT PRIMARY KEY,
                    household_id    TEXT NOT NULL,
                    kind            TEXT NOT NULL,
                    label           TEXT NOT NULL,
                    metadata_json   TEXT NOT NULL DEFAULT '{}',
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_home_entities_household_kind
                    ON home_entities(household_id, kind);

                CREATE TABLE IF NOT EXISTS home_relations (
                    id              TEXT PRIMARY KEY,
                    household_id    TEXT NOT NULL,
                    src_entity_id   TEXT NOT NULL,
                    predicate       TEXT NOT NULL,
                    dst_entity_id   TEXT NOT NULL,
                    confidence      REAL NOT NULL DEFAULT 1.0,
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE,
                    FOREIGN KEY (src_entity_id) REFERENCES home_entities(id) ON DELETE CASCADE,
                    FOREIGN KEY (dst_entity_id) REFERENCES home_entities(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_home_relations_lookup
                    ON home_relations(household_id, predicate);

                -- status ∈ {pending, confirmed, dismissed, executed, failed}
                CREATE TABLE IF NOT EXISTS action_drafts (
                    id                  TEXT PRIMARY KEY,
                    user_id             TEXT NOT NULL,
                    session_id          TEXT,
                    tool_name           TEXT NOT NULL,
                    tool_args_json      TEXT NOT NULL,
                    summary             TEXT NOT NULL,
                    status              TEXT NOT NULL DEFAULT 'pending',
                    created_at          TEXT NOT NULL,
                    expires_at          TEXT,
                    edited_args_json    TEXT,
                    error_text          TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_drafts_user_status
                    ON action_drafts(user_id, status, created_at DESC);

                -- outcome ∈ {success, drafted, need_info, deferred, max_steps,
                --            error, suppressed}
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id                      TEXT PRIMARY KEY,
                    user_id                 TEXT NOT NULL,
                    household_id            TEXT,
                    trigger_kind            TEXT NOT NULL,
                    trigger_payload_json    TEXT NOT NULL DEFAULT '{}',
                    plan_json               TEXT NOT NULL DEFAULT '[]',
                    outcome                 TEXT,
                    steps                   INTEGER NOT NULL DEFAULT 0,
                    quality_json            TEXT,
                    campaign_id             TEXT,
                    started_at              TEXT NOT NULL,
                    ended_at                TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_agent_sessions_user_started
                    ON agent_sessions(user_id, started_at DESC);

                -- approval ∈ {auto, draft, deny}
                CREATE TABLE IF NOT EXISTS agent_tool_calls (
                    id              TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    idx             INTEGER NOT NULL,
                    tool_name       TEXT NOT NULL,
                    args_json       TEXT NOT NULL,
                    result_json     TEXT,
                    approval        TEXT NOT NULL,
                    executed_at     TEXT NOT NULL,
                    error_text      TEXT,
                    FOREIGN KEY (session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_session
                    ON agent_tool_calls(session_id, idx);

                -- status ∈ {open, blocked, complete, expired, cancelled}
                CREATE TABLE IF NOT EXISTS agent_campaigns (
                    id                  TEXT PRIMARY KEY,
                    user_id             TEXT NOT NULL,
                    household_id        TEXT,
                    intent              TEXT NOT NULL,
                    summary             TEXT,
                    status              TEXT NOT NULL DEFAULT 'open',
                    watcher_json        TEXT NOT NULL DEFAULT '{}',
                    created_at          TEXT NOT NULL,
                    expires_at          TEXT,
                    parent_session_id   TEXT,
                    closed_at           TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_campaigns_user_status
                    ON agent_campaigns(user_id, status, expires_at);

                CREATE TABLE IF NOT EXISTS agent_campaign_steps (
                    id              TEXT PRIMARY KEY,
                    campaign_id     TEXT NOT NULL,
                    session_id      TEXT,
                    idx             INTEGER NOT NULL,
                    summary         TEXT NOT NULL,
                    completed_at    TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES agent_campaigns(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS agent_cost_ledger (
                    id              TEXT PRIMARY KEY,
                    user_id         TEXT NOT NULL,
                    day             TEXT NOT NULL,
                    integration     TEXT NOT NULL,
                    cost_usd        REAL NOT NULL DEFAULT 0.0,
                    calls           INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_cost_ledger_user_day
                    ON agent_cost_ledger(user_id, day);

                -- source ∈ {builtin, learned, manual}
                CREATE TABLE IF NOT EXISTS playbooks (
                    id                  TEXT PRIMARY KEY,
                    household_id        TEXT,
                    slug                TEXT NOT NULL,
                    title               TEXT NOT NULL,
                    definition_json     TEXT NOT NULL,
                    source              TEXT NOT NULL DEFAULT 'manual',
                    confidence          REAL NOT NULL DEFAULT 1.0,
                    usage_count         INTEGER NOT NULL DEFAULT 0,
                    success_count       INTEGER NOT NULL DEFAULT 0,
                    enabled             INTEGER NOT NULL DEFAULT 1,
                    created_at          TEXT NOT NULL,
                    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_playbooks_household_slug
                    ON playbooks(household_id, slug);

                CREATE TABLE IF NOT EXISTS ambient_events (
                    id                          TEXT PRIMARY KEY,
                    user_id                     TEXT NOT NULL,
                    household_id                TEXT,
                    source                      TEXT NOT NULL,
                    raw_json                    TEXT NOT NULL,
                    normalized_kind             TEXT,
                    normalized_payload_json     TEXT,
                    processed                   INTEGER NOT NULL DEFAULT 0,
                    processed_at                TEXT,
                    created_at                  TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_ambient_user_processed
                    ON ambient_events(user_id, processed, created_at);

                -- policy_json shape:
                --   {"tools": {"<tool>": "auto"|"draft"|"deny"},
                --    "data_classes_blocked": ["third_party"|"kortex"|...],
                --    "morning_hour": 7, "evening_hour": 21,
                --    "daily_cost_cap_usd": 5.0}
                CREATE TABLE IF NOT EXISTS user_agent_policy (
                    user_id     TEXT PRIMARY KEY,
                    policy_json TEXT NOT NULL DEFAULT '{}',
                    updated_at  TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_tool_stats (
                    user_id             TEXT NOT NULL,
                    tool_name           TEXT NOT NULL,
                    confirmed_count     INTEGER NOT NULL DEFAULT 0,
                    dismissed_count     INTEGER NOT NULL DEFAULT 0,
                    edited_count        INTEGER NOT NULL DEFAULT 0,
                    error_count         INTEGER NOT NULL DEFAULT 0,
                    last_evaluated_at   TEXT,
                    PRIMARY KEY (user_id, tool_name),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS user_oauth_tokens (
                    user_id                     TEXT NOT NULL,
                    provider                    TEXT NOT NULL,
                    access_token_encrypted      TEXT NOT NULL,
                    refresh_token_encrypted     TEXT,
                    expires_at                  TEXT,
                    scopes                      TEXT,
                    PRIMARY KEY (user_id, provider),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            _stamp(5)
        except Exception as exc:
            log.error("schema migration v5 failed: %s", exc)
            raise

    # v6: web push subscriptions
    if 6 not in applied:
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id          TEXT PRIMARY KEY,
                    user_id     TEXT NOT NULL,
                    endpoint    TEXT NOT NULL UNIQUE,
                    p256dh      TEXT NOT NULL,
                    auth        TEXT NOT NULL,
                    user_agent  TEXT,
                    created_at  TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user
                    ON push_subscriptions(user_id);
            """)
            _stamp(6)
        except Exception as exc:
            log.error("schema migration v6 failed: %s", exc)
            raise


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


# ── Rate limiting ──────────────────────────────────────────────────────────────

def record_rate_limit_attempt(bucket: str, key: str) -> None:
    """Persist one attempt for a (bucket, key) pair — survives restarts and shared across workers."""
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO rate_limit_attempts (id, bucket, key, attempt_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), bucket, key, now()),
        )
    conn.close()


def count_recent_rate_limit_attempts(bucket: str, key: str, window_seconds: int) -> int:
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM rate_limit_attempts WHERE bucket=? AND key=? AND attempt_at > ?",
        (bucket, key, cutoff),
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def prune_old_rate_limit_attempts(window_seconds: int = 86400) -> int:
    """Drop attempts older than window_seconds. Run periodically to keep table small."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
    conn = get_connection()
    with conn:
        cur = conn.execute("DELETE FROM rate_limit_attempts WHERE attempt_at < ?", (cutoff,))
    conn.close()
    return cur.rowcount


def verify_password(user: sqlite3.Row, password: str) -> bool:
    return bcrypt.checkpw(password.encode(), user["password_hash"].encode())


def set_kortex_token(user_id: str, token: str) -> None:
    """Persist a user's Kortex personal token, encrypted at rest."""
    from vello.crypto import encrypt
    enc = encrypt(token) if token else ""
    conn = get_connection()
    with conn:
        conn.execute("UPDATE users SET kortex_token=? WHERE id=?", (enc, user_id))
    conn.close()


def change_password(user_id: str, new_password: str) -> None:
    """Hash + persist a new password. Caller is responsible for authorization."""
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    with conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
    conn.close()


# ── Email verification ────────────────────────────────────────────────────────

def set_verification_token(user_id: str, token: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE users SET verification_token=?, verification_sent_at=? WHERE id=?",
            (token, now(), user_id),
        )
    conn.close()


def verify_email_token(token: str) -> Optional[sqlite3.Row]:
    """
    Returns the user row if token is valid and < 24h old; clears the token
    on success. Returns None for unknown/expired tokens.
    """
    from datetime import timedelta
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE verification_token=?", (token,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    sent_at = row["verification_sent_at"]
    try:
        sent_dt = datetime.fromisoformat(sent_at)
    except (TypeError, ValueError):
        conn.close()
        return None
    # SQLite's datetime() returns naive ISO strings; assume UTC so the
    # comparison below doesn't TypeError on offset-aware vs. -naive mismatch.
    if sent_dt.tzinfo is None:
        sent_dt = sent_dt.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - sent_dt > timedelta(hours=24):
        conn.close()
        return None
    with conn:
        conn.execute(
            "UPDATE users SET email_verified=1, verification_token=NULL, "
            "verification_sent_at=NULL WHERE id=?",
            (row["id"],),
        )
    refreshed = conn.execute("SELECT * FROM users WHERE id=?", (row["id"],)).fetchone()
    conn.close()
    return refreshed


# ── Password reset ────────────────────────────────────────────────────────────

def create_password_reset_token(user_id: str) -> str:
    """One-hour TTL. Caller should rate-limit before reaching this."""
    from datetime import timedelta
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO password_reset_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
    conn.close()
    return token


def get_valid_reset_token(token: str) -> Optional[sqlite3.Row]:
    """Returns the row iff the token is unused and not expired."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM password_reset_tokens WHERE token=? AND used=0 AND expires_at > ?",
        (token, now()),
    ).fetchone()
    conn.close()
    return row


def consume_reset_token(token: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute("UPDATE password_reset_tokens SET used=1 WHERE token=?", (token,))
    conn.close()


def get_kortex_token(user_id: str) -> str:
    """Decrypt and return the user's Kortex token, or '' if not connected."""
    from vello.crypto import decrypt
    conn = get_connection()
    row = conn.execute("SELECT kortex_token FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if not row or not row["kortex_token"]:
        return ""
    return decrypt(row["kortex_token"])


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


def get_zone(user_id: str, zone_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM zones WHERE id=? AND user_id=?",
        (zone_id, user_id),
    ).fetchone()
    conn.close()
    return row


# ── Location events ────────────────────────────────────────────────────────────

def record_location_event(user_id: str, zone_id: str, event_type: str,
                           occurred_at: Optional[str] = None) -> str:
    eid = str(uuid.uuid4())
    when = occurred_at or now()
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO location_events (id, user_id, zone_id, event_type, occurred_at) VALUES (?,?,?,?,?)",
            (eid, user_id, zone_id, event_type, when),
        )
    conn.close()
    return eid


def get_recent_location_events(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM location_events WHERE user_id=? ORDER BY occurred_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
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


# ── Households ────────────────────────────────────────────────────────────────

def get_or_create_household(user_id: str) -> sqlite3.Row:
    """One household per owner for MVP. Created lazily on first agent turn."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM households WHERE owner_user_id=? ORDER BY created_at LIMIT 1",
        (user_id,),
    ).fetchone()
    if row:
        conn.close()
        return row
    hid = str(uuid.uuid4())
    user_tz = "UTC"
    user_row = conn.execute("SELECT timezone FROM users WHERE id=?", (user_id,)).fetchone()
    if user_row and "timezone" in user_row.keys() and user_row["timezone"]:
        user_tz = user_row["timezone"]
    with conn:
        conn.execute(
            "INSERT INTO households (id, owner_user_id, timezone, created_at) "
            "VALUES (?, ?, ?, ?)",
            (hid, user_id, user_tz, now()),
        )
    row = conn.execute("SELECT * FROM households WHERE id=?", (hid,)).fetchone()
    conn.close()
    return row


def update_household(household_id: str, **fields) -> None:
    """Update name/address/lat/lng/timezone — only known columns are written."""
    allowed = {"name", "address", "lat", "lng", "timezone"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    cols = ", ".join(f"{k}=?" for k in sets)
    conn = get_connection()
    with conn:
        conn.execute(
            f"UPDATE households SET {cols} WHERE id=?",
            (*sets.values(), household_id),
        )
    conn.close()


def upsert_household_member(household_id: str, kind: str, name: str,
                             relationship: Optional[str] = None,
                             channels: Optional[dict] = None,
                             consent: Optional[dict] = None,
                             notes: Optional[str] = None) -> str:
    """Idempotent on (household_id, name). Returns the member id."""
    import json
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM household_members WHERE household_id=? AND name=?",
        (household_id, name),
    ).fetchone()
    if existing:
        mid = existing["id"]
        sets: list[str] = []
        args: list = []
        if relationship is not None:
            sets.append("relationship=?")
            args.append(relationship)
        if channels is not None:
            sets.append("channels_json=?")
            args.append(json.dumps(channels))
        if consent is not None:
            sets.append("consent_json=?")
            args.append(json.dumps(consent))
        if notes is not None:
            sets.append("notes=?")
            args.append(notes)
        if sets:
            args.append(mid)
            with conn:
                conn.execute(
                    f"UPDATE household_members SET {', '.join(sets)} WHERE id=?",
                    tuple(args),
                )
        conn.close()
        return mid
    mid = str(uuid.uuid4())
    chan_default = json.dumps(channels or {})
    cons_default = json.dumps(consent or {"model": True, "notify": False})
    with conn:
        conn.execute(
            "INSERT INTO household_members (id, household_id, kind, name, relationship, "
            "notes, channels_json, consent_json, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (mid, household_id, kind, name, relationship, notes, chan_default, cons_default, now()),
        )
    conn.close()
    return mid


def list_household_members(household_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM household_members WHERE household_id=? ORDER BY created_at",
        (household_id,),
    ).fetchall()
    conn.close()
    return rows


def get_household_member(member_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM household_members WHERE id=?", (member_id,),
    ).fetchone()
    conn.close()
    return row


def upsert_member_preference(member_id: str, domain: str, key: str, value: str,
                              source: str = "manual") -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO member_preferences (id, member_id, domain, key, value, source, created_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(member_id, domain, key) DO UPDATE SET value=excluded.value, "
            "source=excluded.source",
            (str(uuid.uuid4()), member_id, domain, key, value, source, now()),
        )
    conn.close()


def list_member_preferences(member_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM member_preferences WHERE member_id=? ORDER BY domain, key",
        (member_id,),
    ).fetchall()
    conn.close()
    return rows


# ── Vendors ───────────────────────────────────────────────────────────────────

def create_vendor(household_id: str, name: str, kind: str = "custom",
                  phone: Optional[str] = None, email: Optional[str] = None,
                  source: str = "manual") -> str:
    vid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO vendors (id, household_id, name, kind, phone, email, source, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (vid, household_id, name, kind, phone, email, source, now()),
        )
    conn.close()
    return vid


def list_vendors(household_id: str, kind: Optional[str] = None) -> list[sqlite3.Row]:
    conn = get_connection()
    if kind:
        rows = conn.execute(
            "SELECT * FROM vendors WHERE household_id=? AND kind=? ORDER BY name",
            (household_id, kind),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM vendors WHERE household_id=? ORDER BY name",
            (household_id,),
        ).fetchall()
    conn.close()
    return rows


def get_vendor(vendor_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone()
    conn.close()
    return row


# ── Lists & list items ────────────────────────────────────────────────────────

def get_or_create_list(household_id: str, slug: str, label: Optional[str] = None,
                        kind: str = "custom") -> sqlite3.Row:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM home_lists WHERE household_id=? AND slug=?",
        (household_id, slug),
    ).fetchone()
    if row:
        conn.close()
        return row
    lid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO home_lists (id, household_id, slug, label, kind, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (lid, household_id, slug, label or slug.replace("_", " ").title(), kind, now()),
        )
    row = conn.execute("SELECT * FROM home_lists WHERE id=?", (lid,)).fetchone()
    conn.close()
    return row


def list_lists(household_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM home_lists WHERE household_id=? ORDER BY created_at",
        (household_id,),
    ).fetchall()
    conn.close()
    return rows


def add_list_item(list_id: str, label: str, qty: Optional[str] = None,
                   source: str = "user") -> str:
    iid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO home_list_items (id, list_id, label, qty, source, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (iid, list_id, label, qty, source, now()),
        )
    conn.close()
    return iid


def update_list_item_status(item_id: str, status: str) -> bool:
    """status ∈ {open, done, dropped}. Sets completed_at on done/dropped."""
    if status not in ("open", "done", "dropped"):
        return False
    completed = now() if status != "open" else None
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE home_list_items SET status=?, completed_at=? WHERE id=?",
            (status, completed, item_id),
        )
    conn.close()
    return cur.rowcount > 0


def list_items_for_list(list_id: str, status: Optional[str] = None) -> list[sqlite3.Row]:
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM home_list_items WHERE list_id=? AND status=? ORDER BY created_at",
            (list_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM home_list_items WHERE list_id=? ORDER BY status, created_at",
            (list_id,),
        ).fetchall()
    conn.close()
    return rows


# ── Inventory ─────────────────────────────────────────────────────────────────

def upsert_inventory_item(household_id: str, label: str,
                           est_lifetime_days: Optional[int] = None,
                           low_threshold_days: Optional[int] = None,
                           location_entity_id: Optional[str] = None,
                           source: str = "user") -> str:
    """Idempotent on (household_id, label)."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM inventory_items WHERE household_id=? AND label=?",
        (household_id, label),
    ).fetchone()
    if existing:
        iid = existing["id"]
        sets: list[str] = []
        args: list = []
        if est_lifetime_days is not None:
            sets.append("est_lifetime_days=?"); args.append(est_lifetime_days)
        if low_threshold_days is not None:
            sets.append("low_threshold_days=?"); args.append(low_threshold_days)
        if location_entity_id is not None:
            sets.append("location_entity_id=?"); args.append(location_entity_id)
        if sets:
            args.append(iid)
            with conn:
                conn.execute(
                    f"UPDATE inventory_items SET {', '.join(sets)} WHERE id=?",
                    tuple(args),
                )
        conn.close()
        return iid
    iid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO inventory_items (id, household_id, label, location_entity_id, "
            "est_lifetime_days, low_threshold_days, source, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (iid, household_id, label, location_entity_id, est_lifetime_days,
             low_threshold_days, source, now()),
        )
    conn.close()
    return iid


def mark_inventory_used(item_id: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE inventory_items SET last_used_at=? WHERE id=?",
            (now(), item_id),
        )
    conn.close()


def list_inventory(household_id: str, low_stock_only: bool = False) -> list[sqlite3.Row]:
    """Low-stock = last_used_at + (est_lifetime_days - low_threshold_days) <= now,
    OR last_used_at IS NULL when est_lifetime_days set (never-used pending restock).
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM inventory_items WHERE household_id=? ORDER BY label",
        (household_id,),
    ).fetchall()
    conn.close()
    if not low_stock_only:
        return rows
    from datetime import datetime as _dt, timedelta
    out = []
    now_dt = _dt.now(timezone.utc)
    for r in rows:
        if r["est_lifetime_days"] is None:
            continue
        threshold = r["low_threshold_days"] or 7
        if not r["last_used_at"]:
            out.append(r)
            continue
        try:
            last = _dt.fromisoformat(r["last_used_at"])
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            due = last + timedelta(days=r["est_lifetime_days"] - threshold)
            if now_dt >= due:
                out.append(r)
        except (TypeError, ValueError):
            continue
    return out


# ── Home events ───────────────────────────────────────────────────────────────

def upsert_home_event(household_id: str, title: str, when_at: str,
                       kind: str = "custom",
                       vendor_id: Optional[str] = None,
                       member_id: Optional[str] = None,
                       source: str = "user") -> str:
    eid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO home_events (id, household_id, title, when_at, kind, vendor_id, "
            "member_id, source, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (eid, household_id, title, when_at, kind, vendor_id, member_id, source, now()),
        )
    conn.close()
    return eid


def list_home_events(household_id: str, window_hours: int = 168) -> list[sqlite3.Row]:
    """Events from now → now+window_hours."""
    from datetime import datetime as _dt, timedelta
    end = (_dt.now(timezone.utc) + timedelta(hours=window_hours)).isoformat()
    start = _dt.now(timezone.utc).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM home_events WHERE household_id=? AND when_at >= ? AND when_at <= ? "
        "ORDER BY when_at",
        (household_id, start, end),
    ).fetchall()
    conn.close()
    return rows


# ── World model ──────────────────────────────────────────────────────────────

def upsert_home_entity(household_id: str, kind: str, label: str,
                        metadata: Optional[dict] = None) -> str:
    """Idempotent on (household_id, kind, label)."""
    import json
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM home_entities WHERE household_id=? AND kind=? AND label=?",
        (household_id, kind, label),
    ).fetchone()
    if existing:
        eid = existing["id"]
        if metadata is not None:
            with conn:
                conn.execute(
                    "UPDATE home_entities SET metadata_json=? WHERE id=?",
                    (json.dumps(metadata), eid),
                )
        conn.close()
        return eid
    eid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO home_entities (id, household_id, kind, label, metadata_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (eid, household_id, kind, label, json.dumps(metadata or {}), now()),
        )
    conn.close()
    return eid


def upsert_home_relation(household_id: str, src_entity_id: str, predicate: str,
                          dst_entity_id: str, confidence: float = 1.0) -> str:
    """Idempotent on (household_id, src, predicate, dst). Updates confidence."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM home_relations WHERE household_id=? AND src_entity_id=? "
        "AND predicate=? AND dst_entity_id=?",
        (household_id, src_entity_id, predicate, dst_entity_id),
    ).fetchone()
    if existing:
        rid = existing["id"]
        with conn:
            conn.execute(
                "UPDATE home_relations SET confidence=? WHERE id=?",
                (confidence, rid),
            )
        conn.close()
        return rid
    rid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO home_relations (id, household_id, src_entity_id, predicate, "
            "dst_entity_id, confidence, created_at) VALUES (?,?,?,?,?,?,?)",
            (rid, household_id, src_entity_id, predicate, dst_entity_id, confidence, now()),
        )
    conn.close()
    return rid


def query_home_relations(household_id: str,
                          predicate: Optional[str] = None,
                          src_entity_id: Optional[str] = None,
                          dst_entity_id: Optional[str] = None) -> list[sqlite3.Row]:
    sql = "SELECT * FROM home_relations WHERE household_id=?"
    args: list = [household_id]
    if predicate:
        sql += " AND predicate=?"; args.append(predicate)
    if src_entity_id:
        sql += " AND src_entity_id=?"; args.append(src_entity_id)
    if dst_entity_id:
        sql += " AND dst_entity_id=?"; args.append(dst_entity_id)
    conn = get_connection()
    rows = conn.execute(sql, tuple(args)).fetchall()
    conn.close()
    return rows


def list_home_entities(household_id: str, kind: Optional[str] = None) -> list[sqlite3.Row]:
    conn = get_connection()
    if kind:
        rows = conn.execute(
            "SELECT * FROM home_entities WHERE household_id=? AND kind=? ORDER BY label",
            (household_id, kind),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM home_entities WHERE household_id=? ORDER BY kind, label",
            (household_id,),
        ).fetchall()
    conn.close()
    return rows


# ── Action drafts ─────────────────────────────────────────────────────────────

def create_draft(user_id: str, session_id: Optional[str], tool_name: str,
                  tool_args: dict, summary: str,
                  expires_at: Optional[str] = None) -> str:
    import json
    did = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO action_drafts (id, user_id, session_id, tool_name, tool_args_json, "
            "summary, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
            (did, user_id, session_id, tool_name, json.dumps(tool_args), summary,
             now(), expires_at),
        )
    conn.close()
    return did


def list_drafts(user_id: str, status: str = "pending") -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM action_drafts WHERE user_id=? AND status=? ORDER BY created_at DESC",
        (user_id, status),
    ).fetchall()
    conn.close()
    return rows


def get_draft(user_id: str, draft_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM action_drafts WHERE user_id=? AND id=?",
        (user_id, draft_id),
    ).fetchone()
    conn.close()
    return row


def update_draft_status(draft_id: str, status: str,
                         error_text: Optional[str] = None) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE action_drafts SET status=?, error_text=? WHERE id=?",
            (status, error_text, draft_id),
        )
    conn.close()
    return cur.rowcount > 0


def update_draft_args(draft_id: str, edited_args: dict) -> bool:
    import json
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE action_drafts SET edited_args_json=? WHERE id=?",
            (json.dumps(edited_args), draft_id),
        )
    conn.close()
    return cur.rowcount > 0


# ── Agent sessions & tool calls ──────────────────────────────────────────────

def create_agent_session(user_id: str, household_id: Optional[str],
                          trigger_kind: str, trigger_payload: dict,
                          campaign_id: Optional[str] = None) -> str:
    import json
    sid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO agent_sessions (id, user_id, household_id, trigger_kind, "
            "trigger_payload_json, campaign_id, started_at) VALUES (?,?,?,?,?,?,?)",
            (sid, user_id, household_id, trigger_kind, json.dumps(trigger_payload),
             campaign_id, now()),
        )
    conn.close()
    return sid


def commit_agent_session(session_id: str, outcome: str, steps: int,
                          plan: list, quality: Optional[dict] = None) -> None:
    import json
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE agent_sessions SET outcome=?, steps=?, plan_json=?, quality_json=?, "
            "ended_at=? WHERE id=?",
            (outcome, steps, json.dumps(plan),
             json.dumps(quality) if quality is not None else None,
             now(), session_id),
        )
    conn.close()


def record_tool_call(session_id: str, idx: int, tool_name: str,
                      args: dict, result: Optional[dict],
                      approval: str, error_text: Optional[str] = None) -> str:
    import json
    cid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO agent_tool_calls (id, session_id, idx, tool_name, args_json, "
            "result_json, approval, executed_at, error_text) VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, session_id, idx, tool_name, json.dumps(args),
             json.dumps(result) if result is not None else None,
             approval, now(), error_text),
        )
    conn.close()
    return cid


def get_agent_session(session_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM agent_sessions WHERE id=?", (session_id,)
    ).fetchone()
    conn.close()
    return row


def list_agent_sessions(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM agent_sessions WHERE user_id=? ORDER BY started_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_recent_tool_calls(user_id: str, minutes: int = 60,
                           limit: int = 20) -> list[sqlite3.Row]:
    """Most-recent tool calls across all sessions, joined with session for filtering."""
    from datetime import datetime as _dt, timedelta
    cutoff = (_dt.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    conn = get_connection()
    rows = conn.execute(
        "SELECT tc.* FROM agent_tool_calls tc "
        "JOIN agent_sessions s ON tc.session_id = s.id "
        "WHERE s.user_id=? AND tc.executed_at > ? "
        "ORDER BY tc.executed_at DESC LIMIT ?",
        (user_id, cutoff, limit),
    ).fetchall()
    conn.close()
    return rows


# ── Agent campaigns ──────────────────────────────────────────────────────────

def create_campaign(user_id: str, household_id: Optional[str], intent: str,
                     watcher: dict, summary: Optional[str] = None,
                     expires_in_days: int = 60,
                     parent_session_id: Optional[str] = None) -> str:
    import json
    from datetime import datetime as _dt, timedelta
    cid = str(uuid.uuid4())
    expires = (_dt.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO agent_campaigns (id, user_id, household_id, intent, summary, "
            "watcher_json, created_at, expires_at, parent_session_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, user_id, household_id, intent, summary, json.dumps(watcher),
             now(), expires, parent_session_id),
        )
    conn.close()
    return cid


def list_open_campaigns(user_id: str) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM agent_campaigns WHERE user_id=? AND status='open' "
        "ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_campaign(campaign_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM agent_campaigns WHERE id=?", (campaign_id,)
    ).fetchone()
    conn.close()
    return row


def close_campaign(campaign_id: str, status: str = "complete") -> bool:
    if status not in ("complete", "cancelled", "expired", "blocked"):
        return False
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE agent_campaigns SET status=?, closed_at=? WHERE id=?",
            (status, now(), campaign_id),
        )
    conn.close()
    return cur.rowcount > 0


def expire_due_campaigns() -> int:
    """Sweeper for the nightly campaign_sweeper job."""
    conn = get_connection()
    with conn:
        cur = conn.execute(
            "UPDATE agent_campaigns SET status='expired', closed_at=? "
            "WHERE status='open' AND expires_at IS NOT NULL AND expires_at <= ?",
            (now(), now()),
        )
    conn.close()
    return cur.rowcount


def append_campaign_step(campaign_id: str, session_id: Optional[str],
                          summary: str) -> str:
    sid = str(uuid.uuid4())
    conn = get_connection()
    next_idx_row = conn.execute(
        "SELECT COALESCE(MAX(idx)+1, 0) AS nx FROM agent_campaign_steps WHERE campaign_id=?",
        (campaign_id,),
    ).fetchone()
    idx = next_idx_row["nx"] if next_idx_row else 0
    with conn:
        conn.execute(
            "INSERT INTO agent_campaign_steps (id, campaign_id, session_id, idx, summary, "
            "completed_at) VALUES (?,?,?,?,?,?)",
            (sid, campaign_id, session_id, idx, summary, now()),
        )
    conn.close()
    return sid


# ── Cost ledger ───────────────────────────────────────────────────────────────

def record_integration_cost(user_id: str, integration: str,
                             cost_usd: float = 0.0, calls: int = 1) -> None:
    """Bumps today's row for (user, integration) — used for daily caps."""
    from datetime import datetime as _dt
    day = _dt.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, cost_usd, calls FROM agent_cost_ledger WHERE user_id=? AND day=? AND integration=?",
        (user_id, day, integration),
    ).fetchone()
    with conn:
        if existing:
            conn.execute(
                "UPDATE agent_cost_ledger SET cost_usd=?, calls=? WHERE id=?",
                (existing["cost_usd"] + cost_usd, existing["calls"] + calls, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO agent_cost_ledger (id, user_id, day, integration, cost_usd, calls) "
                "VALUES (?,?,?,?,?,?)",
                (str(uuid.uuid4()), user_id, day, integration, cost_usd, calls),
            )
    conn.close()


def get_today_cost(user_id: str) -> float:
    from datetime import datetime as _dt
    day = _dt.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) AS total FROM agent_cost_ledger "
        "WHERE user_id=? AND day=?",
        (user_id, day),
    ).fetchone()
    conn.close()
    return float(row["total"] if row else 0.0)


# ── Trust stats & policy ─────────────────────────────────────────────────────

def get_user_policy(user_id: str) -> dict:
    """Returns parsed policy_json or default empty per-tool overrides."""
    import json
    conn = get_connection()
    row = conn.execute(
        "SELECT policy_json FROM user_agent_policy WHERE user_id=?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {}
    try:
        return json.loads(row["policy_json"]) or {}
    except (ValueError, TypeError):
        return {}


def set_user_policy(user_id: str, policy: dict) -> None:
    import json
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO user_agent_policy (user_id, policy_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET policy_json=excluded.policy_json, "
            "updated_at=excluded.updated_at",
            (user_id, json.dumps(policy), now()),
        )
    conn.close()


def get_tool_stats(user_id: str, tool_name: Optional[str] = None) -> list[sqlite3.Row]:
    conn = get_connection()
    if tool_name:
        rows = conn.execute(
            "SELECT * FROM user_tool_stats WHERE user_id=? AND tool_name=?",
            (user_id, tool_name),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM user_tool_stats WHERE user_id=?", (user_id,),
        ).fetchall()
    conn.close()
    return rows


def bump_tool_stat(user_id: str, tool_name: str, kind: str) -> None:
    """kind ∈ {confirmed, dismissed, edited, error}."""
    if kind not in ("confirmed", "dismissed", "edited", "error"):
        return
    column = f"{kind}_count"
    conn = get_connection()
    with conn:
        cur = conn.execute(
            f"UPDATE user_tool_stats SET {column}={column}+1, last_evaluated_at=? "
            "WHERE user_id=? AND tool_name=?",
            (now(), user_id, tool_name),
        )
        if cur.rowcount == 0:
            init = {"confirmed": 0, "dismissed": 0, "edited": 0, "error": 0}
            init[kind] = 1
            conn.execute(
                "INSERT INTO user_tool_stats (user_id, tool_name, confirmed_count, "
                "dismissed_count, edited_count, error_count, last_evaluated_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (user_id, tool_name, init["confirmed"], init["dismissed"],
                 init["edited"], init["error"], now()),
            )
    conn.close()


def count_recent_dismissals(user_id: str, tool_name: str, days: int = 7) -> int:
    """Count dismissals via drafts table — more accurate than a roll-up."""
    from datetime import datetime as _dt, timedelta
    cutoff = (_dt.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM action_drafts WHERE user_id=? AND tool_name=? "
        "AND status='dismissed' AND created_at > ?",
        (user_id, tool_name, cutoff),
    ).fetchone()
    conn.close()
    return int(row["n"] if row else 0)


def count_recent_tool_errors(user_id: str, tool_name: str, hours: int = 1) -> int:
    from datetime import datetime as _dt, timedelta
    cutoff = (_dt.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM agent_tool_calls tc "
        "JOIN agent_sessions s ON s.id = tc.session_id "
        "WHERE s.user_id=? AND tc.tool_name=? AND tc.error_text IS NOT NULL "
        "AND tc.executed_at > ?",
        (user_id, tool_name, cutoff),
    ).fetchone()
    conn.close()
    return int(row["n"] if row else 0)


# ── OAuth tokens ─────────────────────────────────────────────────────────────

def set_oauth_token(user_id: str, provider: str, access_token: str,
                     refresh_token: Optional[str] = None,
                     expires_at: Optional[str] = None,
                     scopes: Optional[str] = None) -> None:
    """Tokens encrypted via vello.crypto before persistence."""
    from vello.crypto import encrypt
    enc_access = encrypt(access_token)
    enc_refresh = encrypt(refresh_token) if refresh_token else None
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO user_oauth_tokens (user_id, provider, access_token_encrypted, "
            "refresh_token_encrypted, expires_at, scopes) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(user_id, provider) DO UPDATE SET "
            "access_token_encrypted=excluded.access_token_encrypted, "
            "refresh_token_encrypted=excluded.refresh_token_encrypted, "
            "expires_at=excluded.expires_at, scopes=excluded.scopes",
            (user_id, provider, enc_access, enc_refresh, expires_at, scopes),
        )
    conn.close()


def get_oauth_token(user_id: str, provider: str) -> Optional[dict]:
    """Returns decrypted tokens or None. Caller decides on refresh."""
    from vello.crypto import decrypt
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_oauth_tokens WHERE user_id=? AND provider=?",
        (user_id, provider),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        access = decrypt(row["access_token_encrypted"])
        refresh = decrypt(row["refresh_token_encrypted"]) if row["refresh_token_encrypted"] else None
    except Exception:
        return None
    return {
        "access_token":  access,
        "refresh_token": refresh,
        "expires_at":    row["expires_at"],
        "scopes":        row["scopes"],
    }


# ── Ambient events ───────────────────────────────────────────────────────────

def record_ambient_event(user_id: str, household_id: Optional[str],
                          source: str, raw: dict) -> str:
    import json
    eid = str(uuid.uuid4())
    conn = get_connection()
    with conn:
        conn.execute(
            "INSERT INTO ambient_events (id, user_id, household_id, source, raw_json, "
            "created_at) VALUES (?,?,?,?,?,?)",
            (eid, user_id, household_id, source, json.dumps(raw), now()),
        )
    conn.close()
    return eid


def list_unprocessed_ambient(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM ambient_events WHERE user_id=? AND processed=0 "
        "ORDER BY created_at LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def mark_ambient_processed(event_id: str, normalized_kind: Optional[str] = None,
                             normalized_payload: Optional[dict] = None) -> None:
    import json
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE ambient_events SET processed=1, processed_at=?, normalized_kind=?, "
            "normalized_payload_json=? WHERE id=?",
            (now(), normalized_kind,
             json.dumps(normalized_payload) if normalized_payload else None,
             event_id),
        )
    conn.close()


# ── Playbooks ────────────────────────────────────────────────────────────────

def upsert_playbook(household_id: Optional[str], slug: str, title: str,
                     definition: dict, source: str = "manual",
                     confidence: float = 1.0) -> str:
    """Idempotent on (household_id, slug). Used by builtin playbook seeding."""
    import json
    conn = get_connection()
    if household_id:
        existing = conn.execute(
            "SELECT id FROM playbooks WHERE household_id=? AND slug=?",
            (household_id, slug),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id FROM playbooks WHERE household_id IS NULL AND slug=?",
            (slug,),
        ).fetchone()
    if existing:
        pid = existing["id"]
        with conn:
            conn.execute(
                "UPDATE playbooks SET title=?, definition_json=?, source=?, "
                "confidence=? WHERE id=?",
                (title, json.dumps(definition), source, confidence, pid),
            )
        conn.close()
        return pid
    pid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO playbooks (id, household_id, slug, title, definition_json, "
            "source, confidence, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (pid, household_id, slug, title, json.dumps(definition), source,
             confidence, now()),
        )
    conn.close()
    return pid


def list_playbooks(household_id: Optional[str] = None,
                    enabled_only: bool = True) -> list[sqlite3.Row]:
    conn = get_connection()
    sql = "SELECT * FROM playbooks WHERE 1=1"
    args: list = []
    if household_id is not None:
        sql += " AND (household_id=? OR household_id IS NULL)"
        args.append(household_id)
    if enabled_only:
        sql += " AND enabled=1"
    sql += " ORDER BY slug"
    rows = conn.execute(sql, tuple(args)).fetchall()
    conn.close()
    return rows


def find_playbook_by_slug(household_id: Optional[str], slug: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM playbooks WHERE slug=? AND (household_id=? OR household_id IS NULL) "
        "ORDER BY (household_id IS NOT NULL) DESC LIMIT 1",
        (slug, household_id),
    ).fetchone()
    conn.close()
    return row
