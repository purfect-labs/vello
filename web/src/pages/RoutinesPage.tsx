import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import type { Routine, Zone, Contact } from "../types";
import { V } from "../vello-tokens";

const ROUTINE_TYPES = ["workout", "commute", "morning", "sleep", "medication", "custom"];
const ZONE_TYPES    = ["home", "work", "gym", "custom"];
const NOTIFY_MODES  = [
  { value: "confirm", label: "Ask me first" },
  { value: "auto",    label: "Send automatically" },
  { value: "draft",   label: "Draft only" },
];

function Mono({ children, size = 10, color, style }: {
  children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties;
}) {
  return <span style={{ fontFamily: V.mono, fontSize: size, color: color || V.inkDim, letterSpacing: "0.04em", ...style }}>{children}</span>;
}

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <Mono size={10} color={V.inkFaint} style={{ letterSpacing: "0.2em", textTransform: "uppercase", display: "block", marginBottom: 14 }}>
      {children}
    </Mono>
  );
}

const INPUT: React.CSSProperties = {
  background: V.surfaceHi, border: `1px solid ${V.border}`,
  borderRadius: 10, padding: "9px 14px", fontSize: 13, color: V.ink,
  outline: "none", width: "100%", fontFamily: "inherit",
};

const SELECT: React.CSSProperties = { ...INPUT, cursor: "pointer" };

function ItemRow({ left, right, onDelete }: {
  left: React.ReactNode; right?: React.ReactNode; onDelete: () => void;
}) {
  const [hover, setHover] = useState(false);
  return (
    <div style={{
      background: V.surface, border: `1px solid ${V.border}`, borderRadius: 12,
      padding: "14px 18px", display: "flex", alignItems: "center", justifyContent: "space-between",
    }}>
      <div style={{ flex: 1 }}>{left}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {right}
        <button
          onClick={onDelete}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          style={{
            fontFamily: V.mono, fontSize: 14, color: hover ? V.bad : V.inkFaint,
            background: "none", border: "none", cursor: "pointer", transition: "color .15s",
          }}>×</button>
      </div>
    </div>
  );
}

function AddForm({ fields, onSubmit, onCancel, saving }: {
  fields: React.ReactNode; onSubmit: () => void; onCancel: () => void; saving: boolean;
}) {
  return (
    <div style={{
      background: V.surface, border: `1px solid ${V.borderHi}`,
      borderRadius: 12, padding: 18, display: "flex", flexDirection: "column", gap: 10,
    }}>
      {fields}
      <div style={{ display: "flex", gap: 8 }}>
        <PrimaryBtn onClick={onSubmit} disabled={saving}>{saving ? "…" : "add"}</PrimaryBtn>
        <GhostBtn onClick={onCancel}>cancel</GhostBtn>
      </div>
    </div>
  );
}

function PrimaryBtn({ children, onClick, disabled }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
}) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      fontFamily: V.sans, fontSize: 13, fontWeight: 600,
      color: "#100c06", background: disabled ? V.inkFaint : V.ink,
      border: "none", borderRadius: 999, padding: "8px 18px",
      cursor: disabled ? "default" : "pointer", transition: "background .2s",
    }}>{children}</button>
  );
}

function GhostBtn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.sans, fontSize: 13, fontWeight: 500,
        color: V.ink, background: "transparent",
        border: `1px solid ${hover ? V.borderHi : V.border}`,
        borderRadius: 999, padding: "7px 16px",
        cursor: "pointer", transition: "border-color .2s",
      }}>{children}</button>
  );
}

function AddBtn({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.mono, fontSize: 11, letterSpacing: "0.14em",
        color: hover ? V.inkDim : V.inkFaint,
        background: "transparent", border: `1px solid ${hover ? V.border : "transparent"}`,
        borderRadius: 8, padding: "6px 12px",
        cursor: "pointer", transition: "all .2s", textTransform: "uppercase" as const,
      }}>{children}</button>
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
    api.routines.list().then(r => setRoutines(r as Routine[])).catch(() => {});
    api.zones.list().then(z => setZones(z as Zone[])).catch(() => {});
    api.contacts.list().then(c => setContacts(c as Contact[])).catch(() => {});
  }, []);

  async function addRoutine() {
    if (!routineName.trim()) return;
    setSaving(true);
    const { id } = await api.routines.create({ name: routineName, type: routineType });
    setRoutines(r => [...r, { id, name: routineName, type: routineType, schedule: {}, active: true, confidence: 1, source: "manual", created_at: new Date().toISOString() }]);
    setRoutineName(""); setShowRoutineForm(false); setSaving(false);
  }

  async function toggleRoutine(id: string, active: boolean) {
    await api.routines.toggle(id, active).catch(() => {});
    setRoutines(r => r.map(x => x.id === id ? { ...x, active } : x));
  }

  async function deleteRoutine(id: string) {
    await api.routines.delete(id).catch(() => {});
    setRoutines(r => r.filter(x => x.id !== id));
  }

  async function addZone() {
    if (!zoneLabel.trim()) return;
    setSaving(true);
    const { id } = await api.zones.create({ label: zoneLabel, type: zoneType, address: zoneAddress || undefined });
    setZones(z => [...z, { id, label: zoneLabel, type: zoneType as Zone["type"], address: zoneAddress || null, lat: null, lng: null, radius_meters: 200, created_at: new Date().toISOString() }]);
    setZoneLabel(""); setZoneAddress(""); setShowZoneForm(false); setSaving(false);
  }

  async function addContact() {
    if (!contactName.trim() || !contactLabel.trim()) return;
    setSaving(true);
    const { id } = await api.contacts.create({ label: contactLabel, name: contactName, phone: contactPhone || undefined, notify_mode: contactMode });
    setContacts(c => [...c, { id, label: contactLabel, name: contactName, phone: contactPhone || null, notify_mode: contactMode as Contact["notify_mode"], created_at: new Date().toISOString() }]);
    setContactLabel(""); setContactName(""); setContactPhone(""); setShowContactForm(false); setSaving(false);
  }

  return (
    <div style={{ minHeight: "100vh", background: V.bg, display: "flex", flexDirection: "column" }}>
      <Nav />
      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", padding: "52px 24px" }}>

        <div style={{ marginBottom: 52 }}>
          <span style={{ fontFamily: V.mono, fontSize: 10, letterSpacing: "0.2em", color: V.inkFaint, textTransform: "uppercase" }}>routines & zones</span>
          <h1 style={{ margin: "14px 0 0", fontFamily: V.serif, fontWeight: 400, fontSize: "clamp(32px, 4vw, 44px)", color: V.ink, letterSpacing: "-0.02em", lineHeight: 1 }}>
            daily structure.
          </h1>
        </div>

        {/* Routines */}
        <section style={{ marginBottom: 52 }}>
          <SectionHeader>routines</SectionHeader>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {routines.map(r => (
              <ItemRow key={r.id}
                left={
                  <>
                    <p style={{ margin: "0 0 2px", fontSize: 14, color: r.active ? V.ink : V.inkFaint, fontFamily: V.sans }}>{r.name}</p>
                    <Mono size={10} color={V.inkFaint}>{r.type}</Mono>
                  </>
                }
                right={
                  <button onClick={() => toggleRoutine(r.id, !r.active)} style={{
                    fontFamily: V.mono, fontSize: 10, letterSpacing: "0.1em",
                    padding: "4px 10px", borderRadius: 999, cursor: "pointer",
                    background: r.active ? V.amberMist : "transparent",
                    border: `1px solid ${r.active ? V.amberSoft : V.border}`,
                    color: r.active ? V.amber : V.inkFaint,
                    transition: "all .15s", textTransform: "uppercase" as const,
                  }}>{r.active ? "active" : "paused"}</button>
                }
                onDelete={() => deleteRoutine(r.id)}
              />
            ))}
            {routines.length === 0 && !showRoutineForm && (
              <p style={{ fontFamily: V.serif, fontStyle: "italic", fontSize: 14, color: V.inkFaint, margin: 0 }}>
                no routines yet. vello will learn them from your behavior, or add one manually.
              </p>
            )}
          </div>
          {showRoutineForm ? (
            <AddForm
              fields={<>
                <input value={routineName} onChange={e => setRoutineName(e.target.value)} placeholder="Routine name (e.g. Evening workout)" style={INPUT} />
                <select value={routineType} onChange={e => setRoutineType(e.target.value)} style={SELECT}>
                  {ROUTINE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </>}
              onSubmit={addRoutine} onCancel={() => setShowRoutineForm(false)} saving={saving}
            />
          ) : (
            <AddBtn onClick={() => setShowRoutineForm(true)}>+ add routine</AddBtn>
          )}
        </section>

        {/* Zones */}
        <section style={{ marginBottom: 52 }}>
          <SectionHeader>geofence zones</SectionHeader>
          <p style={{ margin: "0 0 16px", fontFamily: V.sans, fontSize: 13, color: V.inkDim, lineHeight: 1.55 }}>
            zones let vello know where you are — when you leave work late, arrive at the gym, when you're home.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {zones.map(z => (
              <ItemRow key={z.id}
                left={
                  <>
                    <p style={{ margin: "0 0 2px", fontSize: 14, color: V.ink, fontFamily: V.sans }}>{z.label}</p>
                    <Mono size={10} color={V.inkFaint}>{z.type}{z.address ? ` · ${z.address}` : ""}</Mono>
                  </>
                }
                onDelete={() => { api.zones.delete(z.id); setZones(x => x.filter(i => i.id !== z.id)); }}
              />
            ))}
            {zones.length === 0 && !showZoneForm && (
              <p style={{ fontFamily: V.serif, fontStyle: "italic", fontSize: 14, color: V.inkFaint, margin: 0 }}>
                no zones yet. the android app will add these automatically.
              </p>
            )}
          </div>
          {showZoneForm ? (
            <AddForm
              fields={<>
                <input value={zoneLabel} onChange={e => setZoneLabel(e.target.value)} placeholder="Label (e.g. Home, Office)" style={INPUT} />
                <select value={zoneType} onChange={e => setZoneType(e.target.value)} style={SELECT}>
                  {ZONE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input value={zoneAddress} onChange={e => setZoneAddress(e.target.value)} placeholder="Address (optional)" style={INPUT} />
              </>}
              onSubmit={addZone} onCancel={() => setShowZoneForm(false)} saving={saving}
            />
          ) : (
            <AddBtn onClick={() => setShowZoneForm(true)}>+ add zone</AddBtn>
          )}
        </section>

        {/* Contacts */}
        <section style={{ marginBottom: 40 }}>
          <SectionHeader>key contacts</SectionHeader>
          <p style={{ margin: "0 0 16px", fontFamily: V.sans, fontSize: 13, color: V.inkDim, lineHeight: 1.55 }}>
            people vello can loop in when relevant. vello never contacts anyone without your approval unless you choose auto-send.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {contacts.map(c => (
              <ItemRow key={c.id}
                left={
                  <>
                    <p style={{ margin: "0 0 2px", fontSize: 14, color: V.ink, fontFamily: V.sans }}>
                      {c.name}
                      <Mono size={10} color={V.inkFaint} style={{ marginLeft: 8 }}>{c.label}</Mono>
                    </p>
                    <Mono size={10} color={V.inkFaint}>
                      {c.phone ?? "no phone"} · {NOTIFY_MODES.find(m => m.value === c.notify_mode)?.label}
                    </Mono>
                  </>
                }
                onDelete={() => { api.contacts.delete(c.id); setContacts(x => x.filter(i => i.id !== c.id)); }}
              />
            ))}
          </div>
          {showContactForm ? (
            <AddForm
              fields={<>
                <input value={contactLabel} onChange={e => setContactLabel(e.target.value)} placeholder="Label (e.g. Partner, Mom)" style={INPUT} />
                <input value={contactName} onChange={e => setContactName(e.target.value)} placeholder="Name" style={INPUT} />
                <input value={contactPhone} onChange={e => setContactPhone(e.target.value)} placeholder="Phone number (optional)" style={INPUT} />
                <select value={contactMode} onChange={e => setContactMode(e.target.value)} style={SELECT}>
                  {NOTIFY_MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                </select>
              </>}
              onSubmit={addContact} onCancel={() => setShowContactForm(false)} saving={saving}
            />
          ) : (
            <AddBtn onClick={() => setShowContactForm(true)}>+ add contact</AddBtn>
          )}
        </section>
      </div>
    </div>
  );
}
