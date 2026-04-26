import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import type { Routine, Zone, Contact } from "../types";
import { colors, typography, radius } from "../design-system";

const ROUTINE_TYPES = ["workout", "commute", "morning", "sleep", "medication", "custom"];
const ZONE_TYPES    = ["home", "work", "gym", "custom"];
const NOTIFY_MODES  = [
  { value: "confirm", label: "Ask me first" },
  { value: "auto",    label: "Send automatically" },
  { value: "draft",   label: "Draft only" },
];

const INPUT: React.CSSProperties = {
  background: colors.elevated, border: `1px solid ${colors.border}`, borderRadius: radius.sm,
  padding: "8px 12px", fontSize: typography.size.base, color: colors.primary, outline: "none", width: "100%",
};
const SELECT: React.CSSProperties = { ...INPUT, cursor: "pointer" };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 48 }}>
      <p style={{ margin: "0 0 16px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.1em" }}>
        {title}
      </p>
      {children}
    </section>
  );
}

export default function RoutinesPage() {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [zones, setZones]       = useState<Zone[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);

  const [showRoutineForm, setShowRoutineForm] = useState(false);
  const [routineName, setRoutineName]         = useState("");
  const [routineType, setRoutineType]         = useState("workout");

  const [showZoneForm, setShowZoneForm] = useState(false);
  const [zoneLabel, setZoneLabel]       = useState("");
  const [zoneType, setZoneType]         = useState("home");
  const [zoneAddress, setZoneAddress]   = useState("");

  const [showContactForm, setShowContactForm] = useState(false);
  const [contactLabel, setContactLabel]       = useState("");
  const [contactName, setContactName]         = useState("");
  const [contactPhone, setContactPhone]       = useState("");
  const [contactMode, setContactMode]         = useState("confirm");

  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.routines.list().then((r) => setRoutines(r as Routine[])).catch(() => {});
    api.zones.list().then((z) => setZones(z as Zone[])).catch(() => {});
    api.contacts.list().then((c) => setContacts(c as Contact[])).catch(() => {});
  }, []);

  async function addRoutine() {
    if (!routineName.trim()) return;
    setSaving(true);
    const { id } = await api.routines.create({ name: routineName, type: routineType });
    setRoutines((r) => [...r, { id, name: routineName, type: routineType, schedule: {}, active: true, confidence: 1, source: "manual", created_at: new Date().toISOString() }]);
    setRoutineName(""); setShowRoutineForm(false); setSaving(false);
  }

  async function toggleRoutine(id: string, active: boolean) {
    await api.routines.toggle(id, active).catch(() => {});
    setRoutines((r) => r.map((x) => x.id === id ? { ...x, active } : x));
  }

  async function deleteRoutine(id: string) {
    await api.routines.delete(id).catch(() => {});
    setRoutines((r) => r.filter((x) => x.id !== id));
  }

  async function addZone() {
    if (!zoneLabel.trim()) return;
    setSaving(true);
    const { id } = await api.zones.create({ label: zoneLabel, type: zoneType, address: zoneAddress || undefined });
    setZones((z) => [...z, { id, label: zoneLabel, type: zoneType as Zone["type"], address: zoneAddress || null, lat: null, lng: null, radius_meters: 200, created_at: new Date().toISOString() }]);
    setZoneLabel(""); setZoneAddress(""); setShowZoneForm(false); setSaving(false);
  }

  async function addContact() {
    if (!contactName.trim() || !contactLabel.trim()) return;
    setSaving(true);
    const { id } = await api.contacts.create({ label: contactLabel, name: contactName, phone: contactPhone || undefined, notify_mode: contactMode });
    setContacts((c) => [...c, { id, label: contactLabel, name: contactName, phone: contactPhone || null, notify_mode: contactMode as Contact["notify_mode"], created_at: new Date().toISOString() }]);
    setContactLabel(""); setContactName(""); setContactPhone(""); setShowContactForm(false); setSaving(false);
  }

  const deleteBtn: React.CSSProperties = {
    fontSize: 16, color: colors.faint, background: "none", border: "none", cursor: "pointer", transition: "color 0.15s",
  };

  return (
    <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", padding: "48px 24px" }}>
        <div style={{ marginBottom: 40 }}>
          <p style={{ margin: "0 0 6px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.12em" }}>ROUTINES & ZONES</p>
          <h1 style={{ margin: 0, fontSize: typography.size["2xl"], fontWeight: typography.weight.extrabold, color: colors.white, letterSpacing: "-0.03em" }}>Daily structure</h1>
        </div>

        {/* Routines */}
        <Section title="ROUTINES">
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {routines.map((r) => (
              <div key={r.id} style={{
                background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.md,
                padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div>
                  <p style={{ margin: "0 0 2px", fontSize: typography.size.md, fontWeight: typography.weight.normal, color: r.active ? colors.primary : colors.borderStrong }}>{r.name}</p>
                  <p style={{ margin: 0, fontSize: typography.size.xs, color: colors.muted }}>{r.type}</p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <button
                    onClick={() => toggleRoutine(r.id, !r.active)}
                    style={{
                      fontSize: 11, padding: "4px 10px", borderRadius: radius.full, cursor: "pointer",
                      background: r.active ? "rgba(255,255,255,0.08)" : "transparent",
                      border: "1px solid rgba(255,255,255,0.1)", color: r.active ? colors.primary : colors.muted,
                      transition: "all 0.15s",
                    }}
                  >
                    {r.active ? "Active" : "Paused"}
                  </button>
                  <button onClick={() => deleteRoutine(r.id)} style={deleteBtn}
                    onMouseEnter={(e) => (e.currentTarget.style.color = colors.error)}
                    onMouseLeave={(e) => (e.currentTarget.style.color = colors.faint)}>
                    ×
                  </button>
                </div>
              </div>
            ))}
            {routines.length === 0 && !showRoutineForm && (
              <p style={{ fontSize: typography.size.base, color: colors.borderStrong, margin: 0 }}>No routines yet. Vello will learn them from your behavior, or add one manually.</p>
            )}
          </div>

          {showRoutineForm ? (
            <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.md, padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
              <input value={routineName} onChange={(e) => setRoutineName(e.target.value)} placeholder="Routine name (e.g. Evening workout)" style={INPUT} />
              <select value={routineType} onChange={(e) => setRoutineType(e.target.value)} style={SELECT}>
                {ROUTINE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={addRoutine} disabled={saving} className="btn-primary" style={{ fontSize: 13 }}>{saving ? "…" : "Add"}</button>
                <button onClick={() => setShowRoutineForm(false)} className="btn-ghost" style={{ fontSize: 13 }}>Cancel</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowRoutineForm(true)} className="btn-ghost" style={{ fontSize: 13 }}>+ Add routine</button>
          )}
        </Section>

        {/* Zones */}
        <Section title="GEOFENCE ZONES">
          <p style={{ margin: "0 0 14px", fontSize: typography.size.sm, color: colors.borderStrong, lineHeight: typography.lineHeight.normal }}>
            Zones let Vello know where you are — when you leave work late, when you arrive at the gym, when you're home.
            Coordinates come from the Android app; add them here by address for now.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {zones.map((z) => (
              <div key={z.id} style={{
                background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.md,
                padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div>
                  <p style={{ margin: "0 0 2px", fontSize: typography.size.md, fontWeight: typography.weight.normal, color: colors.primary }}>{z.label}</p>
                  <p style={{ margin: 0, fontSize: typography.size.xs, color: colors.muted }}>
                    {z.type}{z.address ? ` · ${z.address}` : ""}
                  </p>
                </div>
                <button onClick={() => { api.zones.delete(z.id); setZones((x) => x.filter((i) => i.id !== z.id)); }}
                  style={deleteBtn}
                  onMouseEnter={(e) => (e.currentTarget.style.color = colors.error)}
                  onMouseLeave={(e) => (e.currentTarget.style.color = colors.faint)}>
                  ×
                </button>
              </div>
            ))}
            {zones.length === 0 && !showZoneForm && (
              <p style={{ fontSize: typography.size.base, color: colors.borderStrong, margin: 0 }}>No zones yet. The Android app will add these automatically.</p>
            )}
          </div>

          {showZoneForm ? (
            <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.md, padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
              <input value={zoneLabel} onChange={(e) => setZoneLabel(e.target.value)} placeholder="Label (e.g. Home, Office)" style={INPUT} />
              <select value={zoneType} onChange={(e) => setZoneType(e.target.value)} style={SELECT}>
                {ZONE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <input value={zoneAddress} onChange={(e) => setZoneAddress(e.target.value)} placeholder="Address (optional)" style={INPUT} />
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={addZone} disabled={saving} className="btn-primary" style={{ fontSize: 13 }}>{saving ? "…" : "Add zone"}</button>
                <button onClick={() => setShowZoneForm(false)} className="btn-ghost" style={{ fontSize: 13 }}>Cancel</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowZoneForm(true)} className="btn-ghost" style={{ fontSize: 13 }}>+ Add zone</button>
          )}
        </Section>

        {/* Contacts */}
        <Section title="KEY CONTACTS">
          <p style={{ margin: "0 0 14px", fontSize: typography.size.sm, color: colors.borderStrong, lineHeight: typography.lineHeight.normal }}>
            People Vello can loop in when relevant — like letting your partner know you're working late.
            Vello never contacts anyone without your approval unless you choose auto-send.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {contacts.map((c) => (
              <div key={c.id} style={{
                background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.md,
                padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between",
              }}>
                <div>
                  <p style={{ margin: "0 0 2px", fontSize: typography.size.md, fontWeight: typography.weight.normal, color: colors.primary }}>{c.name}
                    <span style={{ marginLeft: 8, fontSize: 11, color: colors.borderStrong }}>{c.label}</span>
                  </p>
                  <p style={{ margin: 0, fontSize: typography.size.xs, color: colors.muted }}>
                    {c.phone ?? "No phone"} · {NOTIFY_MODES.find((m) => m.value === c.notify_mode)?.label}
                  </p>
                </div>
                <button onClick={() => { api.contacts.delete(c.id); setContacts((x) => x.filter((i) => i.id !== c.id)); }}
                  style={deleteBtn}
                  onMouseEnter={(e) => (e.currentTarget.style.color = colors.error)}
                  onMouseLeave={(e) => (e.currentTarget.style.color = colors.faint)}>
                  ×
                </button>
              </div>
            ))}
          </div>

          {showContactForm ? (
            <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.md, padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
              <input value={contactLabel} onChange={(e) => setContactLabel(e.target.value)} placeholder="Label (e.g. Partner, Mom)" style={INPUT} />
              <input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="Name" style={INPUT} />
              <input value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="Phone number (optional)" style={INPUT} />
              <select value={contactMode} onChange={(e) => setContactMode(e.target.value)} style={SELECT}>
                {NOTIFY_MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={addContact} disabled={saving} className="btn-primary" style={{ fontSize: 13 }}>{saving ? "…" : "Add contact"}</button>
                <button onClick={() => setShowContactForm(false)} className="btn-ghost" style={{ fontSize: 13 }}>Cancel</button>
              </div>
            </div>
          ) : (
            <button onClick={() => setShowContactForm(true)} className="btn-ghost" style={{ fontSize: 13 }}>+ Add contact</button>
          )}
        </Section>
      </div>
    </div>
  );
}
