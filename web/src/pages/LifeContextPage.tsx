import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";

const SOURCE_LABEL: Record<string, string> = {
  manual:       "You",
  conversation: "Conversation",
  inferred:     "Observed",
  kortex:       "Kortex",
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
    setData((d) => ({ ...d, [key]: { value: editValue.trim(), source: "manual" } }));
    setEditKey(null);
    setSaving(false);
  }

  async function deleteEntry(key: string) {
    await api.context.delete(domainKey, key).catch(() => {});
    setData((d) => { const n = { ...d }; delete n[key]; return n; });
  }

  return (
    <div style={{
      background: "#0a0a0a", border: "1px solid #1c1c1c",
      borderRadius: 14, overflow: "hidden", transition: "border-color 0.15s",
    }}>
      {/* Card header */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "18px 22px", background: "none", border: "none", cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div>
          <p style={{ margin: "0 0 3px", fontSize: 14, fontWeight: 600, color: "#f5f5f5" }}>
            {domain.label}
          </p>
          <p style={{ margin: 0, fontSize: 12, color: "#505050", lineHeight: 1.4 }}>
            {domain.description}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
          {filledCount > 0 && (
            <span style={{
              fontSize: 11, fontWeight: 600, color: "#888",
              background: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: 100,
            }}>
              {filledCount} / {domain.keys.length}
            </span>
          )}
          <span style={{ color: "#404040", fontSize: 16, transition: "transform 0.2s", transform: open ? "rotate(90deg)" : "none" }}>›</span>
        </div>
      </button>

      {/* Expanded fields */}
      {open && (
        <div style={{ borderTop: "1px solid #1c1c1c" }}>
          {domain.keys.map((key) => {
            const entry = data[key];
            const isEditing = editKey === key;

            return (
              <div key={key} style={{
                padding: "14px 22px",
                borderBottom: "1px solid #111",
                display: "flex", alignItems: "center", gap: 12,
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ margin: "0 0 3px", fontSize: 12, color: "#505050" }}>
                    {KEY_LABELS[key] ?? key}
                  </p>
                  {isEditing ? (
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <input
                        autoFocus
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") saveEdit(key); if (e.key === "Escape") setEditKey(null); }}
                        style={{
                          flex: 1, background: "#111", border: "1px solid #333",
                          borderRadius: 8, padding: "6px 10px", fontSize: 13, color: "#f5f5f5", outline: "none",
                        }}
                      />
                      <button onClick={() => saveEdit(key)} disabled={saving} className="btn-primary" style={{ fontSize: 12, padding: "5px 12px" }}>
                        {saving ? "…" : "Save"}
                      </button>
                      <button onClick={() => setEditKey(null)} className="btn-ghost" style={{ fontSize: 12, padding: "4px 10px" }}>
                        Cancel
                      </button>
                    </div>
                  ) : entry ? (
                    <p style={{ margin: 0, fontSize: 14, color: "#f5f5f5" }}>
                      {entry.value}
                      <span style={{ marginLeft: 8, fontSize: 10, color: "#3a3a3a", fontWeight: 600 }}>
                        {SOURCE_LABEL[entry.source] ?? entry.source}
                      </span>
                    </p>
                  ) : (
                    <p style={{ margin: 0, fontSize: 13, color: "#2a2a2a", fontStyle: "italic" }}>Not set</p>
                  )}
                </div>

                {!isEditing && (
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <button
                      onClick={() => { setEditKey(key); setEditValue(entry?.value ?? ""); }}
                      style={{ fontSize: 11, color: "#404040", background: "none", border: "none", cursor: "pointer", padding: "4px 8px", borderRadius: 6, transition: "color 0.15s" }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = "#f5f5f5")}
                      onMouseLeave={(e) => (e.currentTarget.style.color = "#404040")}
                    >
                      {entry ? "Edit" : "Add"}
                    </button>
                    {entry && (
                      <button
                        onClick={() => deleteEntry(key)}
                        style={{ fontSize: 11, color: "#2a2a2a", background: "none", border: "none", cursor: "pointer", padding: "4px 8px", borderRadius: 6, transition: "color 0.15s" }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
                        onMouseLeave={(e) => (e.currentTarget.style.color = "#2a2a2a")}
                      >
                        ×
                      </button>
                    )}
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

export default function LifeContextPage() {
  const [context, setContext] = useState<Record<string, { label: string; description: string; keys: string[]; data: Record<string, { value: string; source: string }> }>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.context.getAll().then(setContext).finally(() => setLoading(false));
  }, []);

  const totalFilled = Object.values(context).reduce((sum, d) => sum + Object.keys(d.data).length, 0);
  const totalKeys   = Object.values(context).reduce((sum, d) => sum + d.keys.length, 0);

  return (
    <div style={{ minHeight: "100vh", background: "#000", display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", padding: "48px 24px" }}>

        <div style={{ marginBottom: 40 }}>
          <p style={{ margin: "0 0 6px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.12em" }}>LIFE CONTEXT</p>
          <h1 style={{ margin: "0 0 12px", fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.03em" }}>
            What Vello knows about you
          </h1>
          <p style={{ margin: "0 0 20px", fontSize: 14, color: "#505050", lineHeight: 1.6, maxWidth: 560 }}>
            These are the facts Vello has collected — through conversation, observation, or what you've entered here.
            Every field is editable and deletable. Nothing is required.
          </p>
          {!loading && totalFilled > 0 && (
            <p style={{ margin: 0, fontSize: 12, color: "#3a3a3a" }}>
              {totalFilled} of {totalKeys} fields filled — Vello will learn the rest over time.
            </p>
          )}
        </div>

        {loading ? (
          <p style={{ color: "#333", fontSize: 13 }}>Loading…</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {Object.entries(context).map(([key, domain]) => (
              <ContextCard key={key} domainKey={key} domain={domain} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
