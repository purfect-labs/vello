# Vello

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18%2B-61DAFB?logo=react&logoColor=black)
![Claude](https://img.shields.io/badge/Claude-Haiku%20%7C%20Sonnet-8A2BE2?logo=anthropic&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

**A proactive personal life agent.** Vello is not a chatbot. It learns your patterns, monitors your life context, and surfaces what you need before you know you need it.

---

## Philosophy

Most AI tools answer questions. Vello asks a different one: *what should you know right now that you haven't thought to ask?*

The premise is that human life is patterned. You wake at roughly the same time. You hit the gym on certain days. Your work stress spikes before certain cycles. When those patterns break, something is happening — a shift in health, finances, relationships, career. Vello watches for those breaks and surfaces them. It also watches for signals in your own words — phrases that correlate with larger life transitions — and activates downstream monitoring accordingly.

The design is not a reminder app or a to-do list. It is ambient intelligence layered over your actual behavior: inferred from conversation, imported from connected memory engines, observed from geofenced location events, and continuously compared against the baseline you established just by living your life.

Data that isn't acted on doesn't matter. Vello acts.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│   React + TypeScript + Vite  (port 5174)                        │
│   Dashboard │ Dialogue │ Profile │ Routines │ Settings           │
└───────────────────────┬──────────────────────────────────────────┘
                        │ HTTP / JSON (JWT via httpOnly cookie)
┌───────────────────────▼──────────────────────────────────────────┐
│                      FastAPI Backend  (port 8001)                │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │  Auth       │  │  Dialogue    │  │  Signal Pipeline      │   │
│  │  JWT/cookie │  │  Haiku 4.5   │  │  signals.py (8 types) │   │
│  └─────────────┘  └──────────────┘  │  SIGNAL_TRANSITIONS   │   │
│                                     │  Anti-fatigue dedup   │   │
│  ┌─────────────┐  ┌──────────────┐  └───────────────────────┘   │
│  │  Context    │  │  Temporal    │  ┌───────────────────────┐   │
│  │  8 domains  │  │  Pattern Eng │  │  Inference Engine     │   │
│  └─────────────┘  └──────────────┘  │  Sonnet 4.6           │   │
│                                     └───────────────────────┘   │
└───────────────────────┬──────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
┌───────▼──────┐              ┌─────────▼────────┐
│  SQLite WAL  │              │  Kortex Engine   │
│  vello.db    │              │  (optional)      │
│  8 tables    │              │  ktx_ token      │
└──────────────┘              └──────────────────┘
```

**Models:**
- `claude-haiku-4-5-20251001` — dialogue, onboarding, fact extraction (low latency)
- `claude-sonnet-4-6` — agent planning, inference generation, signal interpretation (quality-sensitive)

**Session:** JWT stored in httpOnly cookie, 30-day expiry.

---

## Data Model

### `life_context`
Domain/key/value triplets. The core profile store.

| Column | Type | Notes |
|--------|------|-------|
| `domain` | TEXT | `schedule`, `fitness`, `work`, `finance`, `health`, `home`, `people`, `preferences` |
| `key` | TEXT | Freeform label within domain |
| `value` | TEXT | Stored value |
| `source` | TEXT | `manual`, `conversation`, `inferred`, `kortex` |
| `updated_at` | DATETIME | Last write timestamp |

### `dialogue`
Full conversation history.

| Column | Type | Notes |
|--------|------|-------|
| `role` | TEXT | `user` or `assistant` |
| `content` | TEXT | Raw message text |
| `intent` | TEXT | Classified intent from assistant turn |
| `created_at` | DATETIME | |

### `contacts`
Key people (partner, family, close friends).

| Column | Type | Notes |
|--------|------|-------|
| `name` | TEXT | |
| `relationship` | TEXT | |
| `notify_mode` | TEXT | `confirm` (ask before notifying), `auto` (send directly), `draft` (compose but hold) |

### `routines`
Learned or manually entered schedules.

| Column | Type | Notes |
|--------|------|-------|
| `label` | TEXT | e.g., "Morning gym", "Weekly sync" |
| `schedule_json` | JSON | `{"days": [1,3,5], "time": "07:30", "window_minutes": 20}` |
| `active` | BOOLEAN | Toggle without deleting |
| `confidence` | FLOAT | 0.0–1.0; learned routines start lower |

### `zones`
Geofenced locations.

| Column | Type | Notes |
|--------|------|-------|
| `label` | TEXT | |
| `zone_type` | TEXT | `home`, `work`, `gym`, `custom` |
| `lat` | FLOAT | |
| `lng` | FLOAT | |
| `radius_meters` | INT | |

### `location_events`
Enter/exit events from mobile geofencing.

| Column | Type | Notes |
|--------|------|-------|
| `zone_id` | INT | FK → zones |
| `event_type` | TEXT | `enter` or `exit` |
| `occurred_at` | DATETIME | |

### `pending_inferences`
AI-proposed profile changes awaiting user decision.

| Column | Type | Notes |
|--------|------|-------|
| `type` | TEXT | `inference` (new insight) or `contradiction` (conflict with existing value) |
| `description` | TEXT | Human-readable explanation |
| `proposed_json` | JSON | The update to apply on confirm |
| `status` | TEXT | `pending`, `confirmed`, `dismissed` |

### `action_log`
Append-only audit trail.

| Column | Type | Notes |
|--------|------|-------|
| `action_type` | TEXT | What happened |
| `detail_json` | JSON | Full context |
| `created_at` | DATETIME | |

---

## Signal Pipeline

Signals are behavioral intent markers detected from text — conversation and imported Kortex data.

### Signal Library (`signals.py`)

| Signal ID | Trigger examples |
|-----------|-----------------|
| `travel_planned` | "flying to", "hotel in", "layover", "TSA pre" |
| `job_change` | "new job", "quit", "offer letter", "first day at" |
| `moving_home` | "signed a lease", "movers", "new apartment", "closing on" |
| `relationship_change` | "we broke up", "getting married", "she moved in" |
| `health_event` | "diagnosed with", "surgery", "starting medication" |
| `financial_shift` | "paid off", "new account", "refinancing", "big raise" |
| `schedule_disruption` | "working from home now", "changed shifts", "no longer doing" |
| `large_purchase` | "bought a car", "new laptop", "ordered a" |

Patterns are compiled as regexes at module import. Scanner runs against every dialogue message and every Kortex import batch.

### Signal Chaining (`SIGNAL_TRANSITIONS`)

When a signal fires, it activates downstream watches on correlated signals:

| Trigger | Downstream | Watch window |
|---------|-----------|--------------|
| `job_change` | `moving_home` | 45 days (factor=0, bypass dedup) |
| `job_change` | `schedule_disruption` | 7 days |
| `job_change` | `financial_shift` | 60 days |
| `moving_home` | `large_purchase` | 30 days |
| `relationship_change` | `moving_home` | 60 days |
| `health_event` | `schedule_disruption` | 14 days |

Watches with `factor=0` bypass anti-fatigue deduplication — they will surface even if the downstream signal fired recently. This ensures chained signals are not silenced.

### Dashboard Display

Signal triggers surface as priority-coded cards:
- **Red dot** — high priority (immediate life impact)
- **Amber dot** — medium priority (near-term relevance)
- **Gray dot** — low priority (informational)

Each card shows `trigger_message` (natural language), confirm button (logs to `action_log` and clears trigger), dismiss button (clears without logging action). Triggers expire; the `expiry` field controls TTL.

---

## Temporal Pattern Engine

### Observation → Pattern → Prediction

1. **Observe**: `POST /api/v1/temporal/observe` logs a `temporal_observations` record — minutes since midnight, day of week, and a label key (e.g., `gym`, `wake`, `lunch`).

2. **Compute patterns**: `temporal_patterns` tracks `mean_minutes`, `std_dev_minutes`, `sample_count`, and `typical_days` per key.

3. **Bimodal detection**: After accumulation, the engine sorts observations and finds the largest gap. If the gap exceeds 45 minutes and at least 5 samples exist on each side, the key is automatically split into `{key}:early` and `{key}:late` sub-patterns. This handles e.g. a gym habit that alternates between morning and evening sessions.

4. **Deviation detection**: On request, the engine compares the current time against `mean + 1.5σ` for patterns typical on today's day of week. Deviations surface at the top of the dashboard as running-late alerts.

5. **Prediction**: `GET /api/v1/temporal/predict/{key}` returns the predicted next occurrence using the day-appropriate cluster.

---

## Kortex Integration

Vello optionally connects to [Kortex](https://kortex.flexflows.net), a personal memory engine. When connected, Vello pulls structured life data from Kortex and uses it to populate `life_context`, scan for signals, and generate contradiction inferences.

### Connect

```bash
curl -X POST http://localhost:8001/api/v1/kortex/connect \
  -H "Content-Type: application/json" \
  -b "session=<token>" \
  -d '{"token": "ktx_xxxxxxxxxxxxxxxx"}'
```

### Import

Pulls `/vello/export` from the Kortex API. The response is expected to contain:
- `life_context`: domain/key/value entries to upsert
- `facts`: freeform factual strings scanned for signals
- `triples`: structured subject/predicate/object assertions
- `contradictions`: pairs of conflicting claims → creates `pending_inferences` of type `contradiction`

After import, chained signal watches fire immediately if parent signals were detected.

```bash
curl -X POST http://localhost:8001/api/v1/kortex/import \
  -b "session=<token>"
```

### Disconnect

```bash
curl -X DELETE http://localhost:8001/api/v1/kortex/disconnect \
  -b "session=<token>"
```

---

## API Reference

All routes prefixed with `/api/v1`. Authentication via JWT in `session` httpOnly cookie.

### Auth

```bash
# Register
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "hunter2"}'

# Login (sets session cookie)
curl -X POST http://localhost:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"email": "you@example.com", "password": "hunter2"}'

# Current user
curl http://localhost:8001/api/v1/auth/me -b cookies.txt

# Logout
curl -X POST http://localhost:8001/api/v1/auth/logout -b cookies.txt
```

### Dialogue

```bash
# Start onboarding (max 3 exchange sequence: schedule → work → fitness)
curl -X POST http://localhost:8001/api/v1/dialogue/start -b cookies.txt

# Send message — returns extracted facts + suggested follow-up
curl -X POST http://localhost:8001/api/v1/dialogue/send \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "I usually hit the gym at 6:30am on weekdays"}'

# Conversation history
curl http://localhost:8001/api/v1/dialogue/history -b cookies.txt
```

The `send` response includes an `extracted` array of `{domain, key, value}` objects applied to `life_context`, and an optional `follow_up` question Claude has prepared.

### Life Context

```bash
# All context entries
curl http://localhost:8001/api/v1/context -b cookies.txt

# Entries for a specific domain
curl "http://localhost:8001/api/v1/context?domain=fitness" -b cookies.txt

# Create / update entry
curl -X POST http://localhost:8001/api/v1/context \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"domain": "fitness", "key": "gym_days", "value": "Mon,Wed,Fri"}'

# Delete entry
curl -X DELETE http://localhost:8001/api/v1/context/42 -b cookies.txt
```

### Routines

```bash
# List routines
curl http://localhost:8001/api/v1/routines -b cookies.txt

# Create routine
curl -X POST http://localhost:8001/api/v1/routines \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "label": "Morning gym",
    "schedule_json": {"days": [1,3,5], "time": "06:30", "window_minutes": 20},
    "active": true,
    "confidence": 0.9
  }'

# Toggle active
curl -X PATCH http://localhost:8001/api/v1/routines/3/toggle -b cookies.txt

# Delete
curl -X DELETE http://localhost:8001/api/v1/routines/3 -b cookies.txt
```

### Contacts

```bash
# List contacts
curl http://localhost:8001/api/v1/contacts -b cookies.txt

# Create contact
curl -X POST http://localhost:8001/api/v1/contacts \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name": "Alex", "relationship": "partner", "notify_mode": "confirm"}'
```

### Inferences

```bash
# List pending inferences
curl http://localhost:8001/api/v1/inferences -b cookies.txt

# Confirm (applies proposed_json to life_context)
curl -X POST http://localhost:8001/api/v1/inferences/7/confirm -b cookies.txt

# Dismiss
curl -X POST http://localhost:8001/api/v1/inferences/7/dismiss -b cookies.txt
```

### Signals

```bash
# Active signal triggers
curl http://localhost:8001/api/v1/signals -b cookies.txt

# Confirm trigger (logs action, clears trigger)
curl -X POST http://localhost:8001/api/v1/signals/12/confirm -b cookies.txt

# Dismiss trigger
curl -X POST http://localhost:8001/api/v1/signals/12/dismiss -b cookies.txt
```

### Temporal

```bash
# Log an observation
curl -X POST http://localhost:8001/api/v1/temporal/observe \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"key": "gym", "occurred_at": "2026-04-25T06:45:00"}'

# All patterns
curl http://localhost:8001/api/v1/temporal/patterns -b cookies.txt

# Predict next occurrence
curl http://localhost:8001/api/v1/temporal/predict/gym -b cookies.txt

# Current deviations (patterns typical today where you're running late)
curl http://localhost:8001/api/v1/temporal/deviations -b cookies.txt
```

### Zones

```bash
# List zones
curl http://localhost:8001/api/v1/zones -b cookies.txt

# Create zone
curl -X POST http://localhost:8001/api/v1/zones \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "label": "Home",
    "zone_type": "home",
    "lat": 37.7749,
    "lng": -122.4194,
    "radius_meters": 150
  }'

# Log location event (from mobile)
curl -X POST http://localhost:8001/api/v1/zones/5/event \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"event_type": "exit", "occurred_at": "2026-04-25T07:15:00"}'
```

---

## Self-Hosting

### Prerequisites

- Python 3.12+
- Node.js 20+
- An Anthropic API key

### Backend

```bash
git clone <repo>
cd vello

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (see table below)
cp .env.example .env
# Edit .env with your values

# Run
python main.py
# Listening on http://0.0.0.0:8001
```

SQLite WAL mode is enabled automatically. The database file is created at `DB_PATH` on first run.

### Frontend

```bash
cd web

# Install dependencies
npm install

# Development server (proxies API to port 8001)
npm run dev
# http://localhost:5174

# Production build
npm run build
# Output: web/dist/
# Serve dist/ with any static file server; proxy /api/* to port 8001
```

---

## Environment Variables

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `ANTHROPIC_API_KEY` | — | Yes | Anthropic API key for Claude access |
| `SECRET_KEY` | — | Yes | JWT signing secret; use a long random string |
| `DB_PATH` | `vello.db` | No | Path to SQLite database file |
| `CORS_ORIGIN` | `http://localhost:5174` | No | Allowed CORS origin for the frontend |
| `KORTEX_API_URL` | `https://kortex.flexflows.net/api/v1` | No | Kortex API base URL |

Generate a suitable `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Onboarding Flow

New users are guided through a 3-exchange onboarding sequence:

1. **Schedule** — wake time, sleep time, work hours
2. **Work** — role, current projects, stress signals
3. **Fitness** — routine, frequency, goals

Each exchange uses `claude-haiku-4-5-20251001`. The response JSON includes:

```json
{
  "message": "Assistant reply text",
  "extracted": [
    {"domain": "schedule", "key": "wake_time", "value": "06:30"},
    {"domain": "fitness", "key": "gym_frequency", "value": "3x/week"}
  ],
  "follow_up": "What time do you usually wrap up work?",
  "onboarding_complete": false
}
```

Extracted facts are written directly to `life_context` with `source=conversation`. Once `onboarding_complete` is `true`, Vello switches to open contextual learning from ongoing dialogue.

---

## Frontend Pages

### Dashboard
Entry point and primary monitoring surface. Sections render in priority order:

1. **Temporal deviations** — patterns expected today where you haven't yet been observed (running late alerts)
2. **Signal triggers** — active intent signals with priority-coded dots, confirm/dismiss controls
3. **Pending inferences** — AI-proposed profile updates awaiting decision
4. **Quick access grid** — shortcuts to Profile, Routines, Dialogue

### Dialogue
Conversational profile building. Displays conversation history, message input, and real-time extraction feedback showing which facts were pulled from each user message.

### Life Context (Profile)
8-domain grid. Each domain expands to show key/value pairs with inline editing. Source is displayed per entry (manual, conversation, inferred, kortex). Entries can be added or deleted.

### Routines
Two-column list: active routines and inactive routines. Each card shows label, schedule summary, confidence bar, and toggle switch. Confidence is displayed for learned routines to communicate certainty level.

### Settings
- Kortex connection management (connect with token, import, disconnect)
- Account info (email, session details)

---

## Roadmap

**Mobile (Android first, iOS follow-on)**
Real geolocation using device GPS feeds `location_events` natively. Zone enter/exit triggers temporal observations automatically. SMS-based partner notifications via `contacts.notify_mode`.

**Behavioral gap detection**
Compare stated `life_context` values against actual `temporal_patterns`. If you claim to go to the gym 4x/week but observations show 1x, Vello surfaces that discrepancy as a pending inference.

**Values layer**
Infer values from behavioral patterns over time. Consistent late nights on side projects → ambition signal. Frequency of gym skips during high-work weeks → work/health tradeoff pattern. Values are not entered; they are observed.

**Trajectory modeling**
Compute velocity and direction for career, health, and financial domains. Not a snapshot of where you are — a vector of where you are going. Surfaces inflection points and trend reversals.

**Push notifications**
Temporal deviation alerts delivered as push notifications. The dashboard is for when you open Vello; push is for when you haven't.

**Partner sync**
Opt-in shared context for household members. Relevant `life_context` entries and temporal patterns can be shared bidirectionally. Built on the same `contacts` + `notify_mode` model.

**Desktop hub (Electron)**
Background process for macOS/Windows/Linux. Monitors calendar integrations, clipboard context, and app usage patterns. Feeds additional behavioral signal into the temporal engine without requiring mobile.

---

## License

MIT. See `LICENSE`.

---

*Vello is built on the premise that intelligence in your pocket should be working for you constantly, not waiting to be asked.*
