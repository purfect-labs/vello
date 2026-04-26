import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import { V } from "../vello-tokens";

const SOURCE_LABEL: Record<string, string> = {
  manual:       "you",
  conversation: "dialogue",
  inferred:     "observed",
  kortex:       "kortex",
};

const KEY_LABELS: Record<string, string> = {
  wake_time: "Wake time", sleep_goal: "Sleep goal", work_start: "Work start",
  work_end: "Work end", commute_type: "Commute type", commute_minutes: "Commute (min)",
  goal: "Goal", workout_days: "Workout days", workout_time: "Workout time",
  gym_location: "Gym location", weekly_target: "Weekly target", activities: "Activities",
  location_type: "Location type", hybrid_days: "Office days", meeting_style: "Meeting style",
  partner_name: "Partner name", partner_phone: "Partner phone", partner_notify_mode: "Notify mode",
  home_type: "Home type", occupant_count: "People at home", smart_home_platform: "Smart home",
  auto_spend_limit: "Auto-spend limit",
  sleep_quality_goal: "Sleep quality goal", dietary_notes: "Dietary notes",
  brief_style: "Brief style", quiet_start: "Quiet from", quiet_end: "Quiet until",
};

function Mono({ children, size = 10, color, style }: {
  children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties;
}) {
  return (
    <span style={{ fontFamily: V.mono, fontSize: size, color: color || V.inkDim, letterSpacing: "0.04em", ...style }}>
      {children}
    </span>
  );
}

function ContextCard({ domainKey, domain }: {
  domainKey: string;
  domain: { label: string; description: string; keys: string[]; data: Record<string, { value: string; source: string }> };
}) {
  const [open, setOpen]           = useState(false);
  const [editKey, setEditKey]     = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving]       = useState(false);
  const [data, setData]           = useState(domain.data);
  const filledCount = Object.keys(data).length;

  async function saveEdit(key: string) {
    if (!editValue.trim()) return;
    setSaving(true);
    await api.context.upsert(domainKey, key, editValue.trim()).catch(() => {});
    setData(d => ({ ...d, [key]: { value: editValue.trim(), source: "manual" } }));
    setEditKey(null);
    setSaving(false);
  }

  async function deleteEntry(key: string) {
    await api.context.delete(domainKey, key).catch(() => {});
    setData(d => { const n = { ...d }; delete n[key]; return n; });
  }

  return (
    <div style={{
      background: V.surface, border: `1px solid ${open ? V.borderHi : V.border}`,
      borderRadius: 14, overflow: "hidden", transition: "border-color .2s",
    }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "18px 22px", background: "none", border: "none", cursor: "pointer", textAlign: "left",
        }}>
        <div>
          <p style={{ margin: "0 0 3px", fontFamily: V.serif, fontSize: 17, color: V.ink, fontWeight: 400 }}>
            {domain.label}
          </p>
          <p style={{ margin: 0, fontFamily: V.sans, fontSize: 13, color: V.inkDim, lineHeight: 1.4 }}>
            {domain.description}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
          {filledCount > 0 && (
            <Mono size={10} color={V.amber}>
              {filledCount}/{domain.keys.length}
            </Mono>
          )}
          <span style={{
            color: V.inkFaint, fontSize: 14, display: "inline-block",
            transition: "transform 0.2s",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
          }}>›</span>
        </div>
      </button>

      {open && (
        <div style={{ borderTop: `1px solid ${V.hairline}` }}>
          {domain.keys.map(key => {
            const entry = data[key];
            const isEditing = editKey === key;
            return (
              <div key={key} style={{
                padding: "12px 22px",
                borderBottom: `1px solid ${V.hairline}`,
                display: "flex", alignItems: "center", gap: 12,
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <Mono size={10} color={V.inkFaint} style={{ display: "block", marginBottom: 3 }}>
                    {KEY_LABELS[key] ?? key}
                  </Mono>
                  {isEditing ? (
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4 }}>
                      <input
                        autoFocus
                        value={editValue}
                        onChange={e => setEditValue(e.target.value)}
                        onKeyDown={e => { if (e.key === "Enter") saveEdit(key); if (e.key === "Escape") setEditKey(null); }}
                        style={{
                          flex: 1, background: V.surfaceHi, border: `1px solid ${V.borderHi}`,
                          borderRadius: 8, padding: "7px 12px", fontSize: 13,
                          color: V.ink, outline: "none", fontFamily: V.sans,
                        }}
                      />
                      <button onClick={() => saveEdit(key)} disabled={saving} style={smallBtn(V.ink, V.bg)}>
                        {saving ? "…" : "save"}
                      </button>
                      <button onClick={() => setEditKey(null)} style={ghostSmallBtn}>cancel</button>
                    </div>
                  ) : entry ? (
                    <p style={{ margin: 0, fontSize: 14, color: V.ink, fontFamily: V.sans }}>
                      {entry.value}
                      <Mono size={9} color={V.inkFaint} style={{ marginLeft: 8 }}>
                        {SOURCE_LABEL[entry.source] ?? entry.source}
                      </Mono>
                    </p>
                  ) : (
                    <p style={{ margin: 0, fontSize: 13, color: V.inkFaint, fontStyle: "italic", fontFamily: V.serif }}>not set</p>
                  )}
                </div>
                {!isEditing && (
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <EditAction label={entry ? "edit" : "add"} onClick={() => { setEditKey(key); setEditValue(entry?.value ?? ""); }} />
                    {entry && <EditAction label="×" onClick={() => deleteEntry(key)} danger />}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EditAction({ label, onClick, danger }: { label: string; onClick: () => void; danger?: boolean }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.mono, fontSize: 10, letterSpacing: "0.1em",
        color: hover ? (danger ? V.bad : V.ink) : V.inkFaint,
        background: "none", border: "none", cursor: "pointer",
        padding: "4px 8px", borderRadius: 6, transition: "color .15s",
      }}>{label}</button>
  );
}

const smallBtn = (color: string, bg: string): React.CSSProperties => ({
  fontFamily: V.mono, fontSize: 10, letterSpacing: "0.1em",
  color: bg, background: color, border: "none",
  borderRadius: 999, padding: "5px 12px", cursor: "pointer",
});

const ghostSmallBtn: React.CSSProperties = {
  fontFamily: V.mono, fontSize: 10, letterSpacing: "0.1em",
  color: V.inkDim, background: "transparent",
  border: `1px solid ${V.border}`, borderRadius: 999,
  padding: "4px 10px", cursor: "pointer",
};

export default function LifeContextPage() {
  const [context, setContext] = useState<Record<string, {
    label: string; description: string; keys: string[];
    data: Record<string, { value: string; source: string }>;
  }>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.context.getAll().then(setContext).finally(() => setLoading(false));
  }, []);

  const totalFilled = Object.values(context).reduce((s, d) => s + Object.keys(d.data).length, 0);
  const totalKeys   = Object.values(context).reduce((s, d) => s + d.keys.length, 0);

  return (
    <div style={{ minHeight: "100vh", background: V.bg, display: "flex", flexDirection: "column" }}>
      <Nav />
      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", padding: "52px 24px" }}>

        <div style={{ marginBottom: 44 }}>
          <span style={{ fontFamily: V.mono, fontSize: 10, letterSpacing: "0.2em", color: V.inkFaint, textTransform: "uppercase" }}>life context</span>
          <h1 style={{ margin: "14px 0 10px", fontFamily: V.serif, fontWeight: 400, fontSize: "clamp(32px, 4vw, 44px)", color: V.ink, letterSpacing: "-0.02em", lineHeight: 1 }}>
            what vello knows about you.
          </h1>
          <p style={{ margin: "0 0 16px", fontFamily: V.sans, fontSize: 14, color: V.inkDim, lineHeight: 1.55, maxWidth: 520 }}>
            collected through conversation, observation, or what you've entered here. every field is editable. nothing is required.
          </p>
          {!loading && totalFilled > 0 && (
            <span style={{ fontFamily: V.mono, fontSize: 10, color: V.amber, letterSpacing: "0.1em" }}>
              {totalFilled} of {totalKeys} fields filled
            </span>
          )}
        </div>

        {loading ? (
          <p style={{ fontFamily: V.mono, fontSize: 11, color: V.inkFaint, letterSpacing: "0.1em" }}>loading…</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {Object.entries(context).map(([key, domain]) => (
              <ContextCard key={key} domainKey={key} domain={domain} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
