import { useEffect, useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import { colors, typography, radius } from "../design-system";

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
      background: colors.surface, border: `1px solid ${colors.border}`,
      borderRadius: radius.lg, overflow: "hidden", transition: "border-color 0.15s",
    }}>
      {/* Card header */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "18px 22px", background: "none", border: "none", cursor: "pointer", textAlign: "left",
        }}
      >
        <div>
          <p style={{ margin: "0 0 3px", fontSize: typography.size.md, fontWeight: typography.weight.semibold, color: colors.primary }}>
            {domain.label}
          </p>
          <p style={{ margin: 0, fontSize: typography.size.sm, color: colors.muted, lineHeight: typography.lineHeight.tight }}>
            {domain.description}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
          {filledCount > 0 && (
            <span style={{
              fontSize: typography.size.xs, fontWeight: typography.weight.semibold, color: "#888",
              background: "rgba(255,255,255,0.06)", padding: "2px 8px", borderRadius: radius.full,
            }}>
              {filledCount} / {domain.keys.length}
            </span>
          )}
          <span style={{ color: colors.borderStrong, fontSize: 16, transition: "transform 0.2s", transform: open ? "rotate(90deg)" : "none" }}>›</span>
        </div>
      </button>

      {/* Expanded fields */}
      {open && (
        <div style={{ borderTop: `1px solid ${colors.border}` }}>
          {domain.keys.map((key) => {
            const entry     = data[key];
            const isEditing = editKey === key;

            return (
              <div key={key} style={{
                padding: "14px 22px", borderBottom: `1px solid ${colors.borderSubtle}`,
                display: "flex", alignItems: "center", gap: 12,
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ margin: "0 0 3px", fontSize: typography.size.sm, color: colors.muted }}>
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
                          flex: 1, background: colors.elevated, border: `1px solid ${colors.borderStrong}`,
                          borderRadius: radius.sm, padding: "6px 10px", fontSize: typography.size.base,
                          color: colors.primary, outline: "none",
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
                    <p style={{ margin: 0, fontSize: typography.size.md, color: colors.primary }}>
                      {entry.value}
                      <span style={{ marginLeft: 8, fontSize: typography.size.xs, color: colors.faint, fontWeight: typography.weight.semibold }}>
                        {SOURCE_LABEL[entry.source] ?? entry.source}
                      </span>
                    </p>
                  ) : (
                    <p style={{ margin: 0, fontSize: typography.size.base, color: colors.faint, fontStyle: "italic" }}>Not set</p>
                  )}
                </div>

                {!isEditing && (
                  <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                    <button
                      onClick={() => { setEditKey(key); setEditValue(entry?.value ?? ""); }}
                      style={{ fontSize: 11, color: colors.borderStrong, background: "none", border: "none", cursor: "pointer", padding: "4px 8px", borderRadius: 6, transition: "color 0.15s" }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = colors.primary)}
                      onMouseLeave={(e) => (e.currentTarget.style.color = colors.borderStrong)}
                    >
                      {entry ? "Edit" : "Add"}
                    </button>
                    {entry && (
                      <button
                        onClick={() => deleteEntry(key)}
                        style={{ fontSize: 11, color: colors.faint, background: "none", border: "none", cursor: "pointer", padding: "4px 8px", borderRadius: 6, transition: "color 0.15s" }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = colors.error)}
                        onMouseLeave={(e) => (e.currentTarget.style.color = colors.faint)}
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
    <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 720, margin: "0 auto", width: "100%", padding: "48px 24px" }}>

        <div style={{ marginBottom: 40 }}>
          <p style={{ margin: "0 0 6px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.12em" }}>LIFE CONTEXT</p>
          <h1 style={{ margin: "0 0 12px", fontSize: typography.size["2xl"], fontWeight: typography.weight.extrabold, color: colors.white, letterSpacing: "-0.03em" }}>
            What Vello knows about you
          </h1>
          <p style={{ margin: "0 0 20px", fontSize: typography.size.md, color: colors.muted, lineHeight: typography.lineHeight.normal, maxWidth: 560 }}>
            These are the facts Vello has collected — through conversation, observation, or what you've entered here.
            Every field is editable and deletable. Nothing is required.
          </p>
          {!loading && totalFilled > 0 && (
            <p style={{ margin: 0, fontSize: typography.size.sm, color: colors.borderStrong }}>
              {totalFilled} of {totalKeys} fields filled — Vello will learn the rest over time.
            </p>
          )}
        </div>

        {loading ? (
          <p style={{ color: colors.borderStrong, fontSize: typography.size.base }}>Loading…</p>
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
