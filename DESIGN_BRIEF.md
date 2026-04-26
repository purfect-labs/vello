# Vello — Claude Design Brief

Point this file at Claude Design and ask it to produce:
1. A revised `web/src/design-system.ts`
2. Rewritten versions of all pages and components listed below

---

## What Vello Is

Vello is a **proactive personal life agent**. It is not a chatbot. It does not wait to be asked.

It learns your patterns — when you wake, when you work out, when you're running late — and surfaces what you need before you think to ask. It watches for life signals in your own words ("new job", "signed a lease", "we broke up") and activates downstream monitoring. It compares what you say about yourself against what it actually observes, and flags the gaps.

The user's relationship with Vello is not transactional. It is ambient. Vello is always on, always accumulating, occasionally presenting. The UI reflects this: it does not demand interaction. It presents, clearly and quietly, what the agent has noticed.

---

## Current Design State

The existing `design-system.ts` establishes the right foundation but needs a full design pass to reach its potential. The current implementation is functional but feels developer-built — tokens are defined but spacing, hierarchy, and visual polish are inconsistent across pages.

**What works and should be kept:**
- Pure black (`#000000`) page root — commit to it
- Monochromatic primary palette — luminance contrast only
- The amber (`#f59e0b`) reserved for alert/gap states only — purposeful, not decorative
- `surfaces.gap` amber-tint panel for behavioral gap cards
- Button pattern: white filled primary (`btn-primary`) + ghost secondary
- Compact density — this is a tool, not a marketing page

**What needs work:**
- No coherent page-level layout system — each page invents its own
- Section labels and page headers are inconsistent
- The nav is minimal to the point of feeling unfinished
- Cards and panels lack depth differentiation — everything is `#0a0a0a` on `#000`
- No visual language for the *proactive* nature of the product — the dashboard looks like any dashboard

---

## Design Direction

**Aesthetic name (for Claude Design to name):** The existing system has no name. Give it one based on what you create.

**Primary direction:** Terminal × premium personal device. Think the intersection of a Bloomberg terminal and a Calm subscription app. Dense information, immediate legibility, zero decoration. Not cold — purposeful warmth through precise craft.

**The proactive UI problem:** Vello surfaces things to you. The dashboard is not a place where the user *does* things — it's a place where Vello *presents* things. The design should feel like receiving a briefing, not filling out a form. Cards that Vello generates should feel slightly different from user-editable content — presented vs. authored.

**Hierarchy of alert types** (top to bottom urgency):
1. **Temporal deviations** — you're running late against your own patterns right now
2. **Behavioral gaps** — stated vs. observed mismatches (amber tint, `surfaces.gap`)
3. **Signal triggers** — life event detection (priority: high/medium/low)
4. **Pending inferences** — AI-proposed profile updates awaiting confirmation

Each type needs a distinct visual treatment. They should not all look like the same card with different text.

**Single accent rule:** Amber (`#f59e0b` / `colors.warning`) is already established as the gap/alert accent and should stay. No other hue should appear unless Claude Design has a strong case for it. If a second accent is introduced, it must be used with equal discipline.

**Typography:** System UI stack is fine. If Claude Design wants to call a specific font, it should be available on Google Fonts and loaded via `index.html`. No web font for body — only consider one for the wordmark or section labels.

---

## Technical Constraints

- **React 18 + TypeScript + Vite**
- **All styling via inline `style={{}}` props** — no Tailwind, no CSS modules, no styled-components. The existing `btn-primary` and `btn-ghost` classes in `index.css` can be kept or redesigned, but the component styling must be inline.
- **Design tokens live in `web/src/design-system.ts`** — all values must be importable from there. Components import `{ colors, typography, radius, surfaces, components }` etc.
- **No polarity system** — Vello is dark-only. No light mode. Do not add a polarity context.
- **`surfaces.*` pattern** — semantic surface objects (e.g. `surfaces.panel`, `surfaces.gap`) are pre-typed as `React.CSSProperties` and spread directly into style props. Keep this pattern.

---

## File Inventory

### `web/src/design-system.ts`
The single source of truth. Currently exports:
- `colors` — bg, surface, surfaceHover, elevated, border variants, text variants, semantic (warning, error, success, white)
- `typography` — fontFamily, wordmark, size scale (xs→3xl), weight, lineHeight
- `spacing` — 4px base unit grid
- `radius` — sm/md/lg/xl/full
- `shadows` — btn primary glow (white bloom), panel
- `transitions` — fast/medium/slow
- `components` — nav, panel, signalCard, gapCard, input, btnPrimary, btnGhost, scrollbar
- `surfaces` — panel, signal, gap, warning, error, success (all typed as `React.CSSProperties`)

Claude Design should revise or replace this entirely.

---

### `web/src/components/Nav.tsx`
**Current state:** Wordmark left, nav links center-right, email + sign out far right. All monochromatic. No active indicator beyond color change.

**Needs:**
- A more considered active state — something more than just `color: white` vs `color: #505050`
- The email display is too prominent — it takes up visual space without value
- The wordmark "VELLO" is bold and letter-spaced — this is good, keep the energy
- Height is 56px — reasonable

---

### `web/src/pages/AuthPage.tsx`
**Current state:** Centered card with tab switcher (Sign in / Create account), email + password fields, submit button.

**Needs:**
- The centered card is the right pattern — this is a focused single-purpose screen
- More considered vertical rhythm and spacing
- The tab switcher (Sign in / Create account) works but feels generic
- Should feel like entering a space, not filling out a form

---

### `web/src/pages/DashboardPage.tsx`
**This is the most important page.**

**Current state:** Greeting header → temporal deviations → behavioral gaps → signal triggers → pending inferences → quick access grid → onboarding nudge.

**Components defined here:**
- `DeviationCard` — running-late alert (amber left-border treatment currently)
- `GapCard` — behavioral gap (uses `surfaces.gap`, amber icon, domain + type label)
- `SignalCard` — signal trigger with priority dot (red/amber/gray) + confirm/dismiss
- `InferenceCard` — Vello noticed something, confirm/dismiss
- Quick access grid — 4 cards: Talk to Vello, Life Context, Routines, Settings

**Needs:**
- The greeting + date header is the right entry point — give it more presence
- The four card types each need a distinct visual treatment — right now they're all variants of the same bordered box
- `DeviationCard` — should feel urgent but not alarming. The `◷` symbol works; the amber border works
- `GapCard` — amber tint background + amber icon is right. Label format is `DOMAIN · TYPE` in all-caps, then description text
- `SignalCard` — priority dot is good. The label + message + confirm/dismiss layout works. High-priority signals should feel more prominent than low
- `InferenceCard` — "VELLO NOTICED" label + description + Looks right / No. This should feel like Vello speaking. The label should have personality
- Quick access grid — currently a 2×2 with icon + title + desc. Functional but could be more considered
- Onboarding nudge — shown only if `!user.onboarding_complete`. Can be subtle — it's not a CTA, it's a nudge

---

### `web/src/pages/DialoguePage.tsx`
**Current state:** Header with VELLO label + "Dialogue" h1 + subtitle. Message thread (bubbles for user, plain text for assistant). Auto-resize textarea + Send button at bottom.

**The assistant label is currently "V"** (single letter, was "K" from a Kortex copy — it's been updated). Should be reconsidered.

**Components:**
- `Bubble` — user messages get rounded bordered bubble; assistant messages are plain text flush left

**Needs:**
- This is a conversation space. It should feel calm and focused — different from the alert-heavy dashboard
- The user bubble vs. assistant text distinction works. Assistant text should feel authoritative but not formal — no speech bubbles for Vello, it speaks plainly
- The input area at the bottom should be considered — this is where the user spends most of their time on this page
- The header doesn't need to be elaborate — this is a focused tool

---

### `web/src/pages/LifeContextPage.tsx`
**Current state:** Page header → list of `ContextCard` components (one per domain, 8 total).

**`ContextCard` component:**
- Collapsible — header shows domain name, description, fill count badge (`n / total`)
- Expanded shows all keys in that domain as rows
- Each row: key label, value (or "Not set" placeholder), source badge (You / Conversation / Observed / Kortex), Edit/Add + × buttons
- Inline edit mode: input field + Save + Cancel per row

**The 8 domains:** schedule, fitness, work, finance, health, home, people, preferences

**Needs:**
- The collapsible card pattern is the right choice for this density
- Source badges matter — distinguish between what the user entered vs. what Vello inferred vs. what came from Kortex
- The expand chevron (`›`) that rotates is fine
- The fill count badge (`n / total`) is useful signal — consider making it more visible
- "Not set" entries feel empty — maybe they should be less prominent than filled entries
- Empty state and loading state need consideration

---

### `web/src/pages/RoutinesPage.tsx`
**Current state:** Three sections — ROUTINES, GEOFENCE ZONES, KEY CONTACTS. Each has a list of items + an "add" form that toggles inline.

**Routine item:** name, type, active/paused toggle pill, × delete
**Zone item:** label, type + address, × delete
**Contact item:** name + label, phone + notify mode, × delete

**Needs:**
- The three-section structure is correct
- Section labels (`ROUTINES`, `GEOFENCE ZONES`, `KEY CONTACTS`) are the right weight — uppercase, small, muted
- The active/paused pill toggle on routines is a good pattern — keep it
- Add forms should feel inline and natural, not like a separate modal landed in the page
- The zones section has a note about Android app / coordinates — this placeholder state needs design consideration (it's a "coming fully" feature)

---

### `web/src/pages/SettingsPage.tsx`
**Current state:** Three `SettingCard` components — Connect Kortex, Account, Android App.

**Kortex card:** Two states — (a) disconnected: token input + connect button, (b) connected: green dot + "Kortex connected" + Sync + Disconnect
**Account card:** Just shows `user.email`
**Android app card:** "Coming soon" with a pulsing dot

**Needs:**
- The `SettingCard` pattern (title + description + content) is clean — keep it
- The Kortex connection states are well-defined — the connected state with the green dot is good
- The "coming soon" Android card should feel forward-looking, not abandoned — it represents real planned functionality

---

## Shell Components to Define

Claude Design should produce these as reusable components or clearly defined patterns. They don't all need to be separate files — they can be defined inline in the pages that use them, as long as the pattern is consistent.

**`PageHeader` pattern** — used at the top of each content page (not the nav). Should have: eyebrow label (e.g. "DASHBOARD"), page title, optional subtitle. Some pages may not need this — Claude Design decides.

**`SectionLabel` pattern** — the uppercase small muted labels that head each section (`RUNNING LATE`, `VELLO DETECTED`, `ROUTINES`, etc.). Should be consistent across all pages.

**`EmptyState` pattern** — for when lists have no items (no routines, no zones, etc.). Currently plain text, needs a considered treatment.

**`StatusDot`** — small colored circle for status indicators (Kortex connected = green, signal priority = red/amber/gray, Android coming soon = white pulsing).

**`SourceBadge`** — in LifeContextPage, each value has a source: You / Conversation / Observed / Kortex. Needs a consistent small badge treatment.

---

## What Claude Design Should Deliver

1. **Revised `web/src/design-system.ts`** — complete replacement. Name the design language. Revise the token set. Keep or replace anything, but it must be internally consistent and exportable.

2. **Rewritten `web/src/components/Nav.tsx`** — using the new tokens.

3. **Rewritten `web/src/pages/AuthPage.tsx`** — using the new tokens.

4. **Rewritten `web/src/pages/DashboardPage.tsx`** — using the new tokens. This is the highest priority page. The four card types (`DeviationCard`, `GapCard`, `SignalCard`, `InferenceCard`) each need a distinct and considered visual treatment.

5. **Rewritten `web/src/pages/DialoguePage.tsx`** — using the new tokens.

6. **Rewritten `web/src/pages/LifeContextPage.tsx`** — using the new tokens.

7. **Rewritten `web/src/pages/RoutinesPage.tsx`** — using the new tokens.

8. **Rewritten `web/src/pages/SettingsPage.tsx`** — using the new tokens.

9. **Revised `web/src/index.css`** — button classes (`btn-primary`, `btn-ghost`) and any global resets or font imports needed by the new design.

---

## Existing `index.css` Reference

```css
/* btn-primary: white filled pill */
.btn-primary {
  background: #ffffff;
  color: #000000;
  font-weight: 700;
  border-radius: 9999px;
  padding: 11px 26px;
  font-size: 13px;
  border: none;
  cursor: pointer;
  transition: box-shadow 0.15s ease, transform 0.15s ease;
  box-shadow: 0 1px 0 rgba(255,255,255,0.08), 0 4px 20px rgba(255,255,255,0.06);
  white-space: nowrap;
}
.btn-primary:hover:not(:disabled) {
  box-shadow: 0 6px 32px rgba(255,255,255,0.20), 0 0 0 1px rgba(255,255,255,0.18);
  transform: translateY(-1px);
}
.btn-primary:active:not(:disabled) {
  box-shadow: 0 1px 8px rgba(255,255,255,0.08);
  transform: translateY(0);
}
.btn-primary:disabled { opacity: 0.35; cursor: not-allowed; }

/* btn-ghost: transparent outlined pill */
.btn-ghost {
  background: transparent;
  color: #f5f5f5;
  font-weight: 600;
  border-radius: 9999px;
  padding: 10px 24px;
  font-size: 13px;
  border: 1px solid rgba(255,255,255,0.12);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
  white-space: nowrap;
}
.btn-ghost:hover:not(:disabled) {
  border-color: rgba(255,255,255,0.25);
  background: rgba(255,255,255,0.05);
}
.btn-ghost:disabled { opacity: 0.35; cursor: not-allowed; }
```

---

## Data Types Reference

```typescript
// The data shapes the UI works with:

interface User { id: string; email: string; onboarding_complete: boolean; has_kortex: boolean; }
interface TemporalDeviation { pattern_key: string; label: string; expected_time: string; current_time: string; late_by_minutes: number; message: string; }
interface BehavioralGap { type: string; domain: string; description: string; pattern_key?: string; }
interface SignalTrigger { id: string; signal_id: string; label: string; priority: "high" | "medium" | "low"; action_type: string; trigger_message: string; created_at: string; expires_at: string; }
interface PendingInference { id: string; inference_type: string; description: string; proposed: Record<string, unknown>; status: string; created_at: string; }
interface DialogueTurn { role: "user" | "assistant"; content: string; created_at: string; }
interface ContextEntry { value: string; source: "manual" | "conversation" | "inferred" | "kortex"; confidence: number; }
interface Routine { id: string; name: string; type: string; schedule: Record<string, unknown>; active: boolean; confidence: number; source: string; created_at: string; }
interface Zone { id: string; label: string; type: "home" | "work" | "gym" | "custom"; address: string | null; lat: number | null; lng: number | null; radius_meters: number; created_at: string; }
interface Contact { id: string; label: string; name: string; phone: string | null; notify_mode: "confirm" | "auto" | "draft"; created_at: string; }
```

---

## Routes

```
/         → DashboardPage
/dialogue → DialoguePage
/profile  → LifeContextPage
/routines → RoutinesPage
/settings → SettingsPage
/login    → AuthPage (mode="login")
/register → AuthPage (mode="register")
```

---

## Context

```typescript
// useAuth() from App.tsx — available anywhere
const { user, loading, refreshUser, logout } = useAuth();

// api.ts — the full API client
import { api } from "../api";
// api.dialogue, api.context, api.routines, api.zones, api.contacts,
// api.inferences, api.signals, api.temporal, api.gaps, api.kortex, api.auth
```

---

*All business logic and API calls in the current pages are correct and should be preserved exactly. Claude Design's job is purely visual — the data fetching, state management, and event handlers stay as-is.*
