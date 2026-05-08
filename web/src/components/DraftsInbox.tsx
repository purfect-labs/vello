import { useState } from "react";
import { api } from "../api";
import { colors, typography, spacing, surfaces, radius, transitions } from "../design-system";

interface Draft {
  id: string;
  tool_name: string;
  summary: string;
  status: string;
  tool_args_json: string;
  created_at: string;
}

interface Props {
  drafts: Draft[];
  onRefresh: () => void;
}

export default function DraftsInbox({ drafts, onRefresh }: Props) {
  const pending = drafts.filter((d) => d.status === "pending");
  if (!pending.length) return null;

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        VELLO WANTS TO DO THIS
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[2] }}>
        {pending.map((d) => <DraftCard key={d.id} draft={d} onRefresh={onRefresh} />)}
      </div>
    </section>
  );
}

function DraftCard({ draft, onRefresh }: { draft: Draft; onRefresh: () => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");

  async function handle(action: "confirm" | "dismiss") {
    setLoading(action); setError(null);
    try {
      if (action === "confirm") await api.drafts.confirm(draft.id);
      else await api.drafts.dismiss(draft.id);
      onRefresh();
    } catch (e: unknown) {
      setError((e as Error).message || "error");
    } finally { setLoading(null); }
  }

  const toolLabel = draft.tool_name.replace(/_/g, " ");
  const isPromotion = draft.tool_name === "__promotion__";

  return (
    <div style={{
      ...surfaces.panel,
      borderLeft: `2px solid rgba(245,158,11,0.5)`,
      padding: `${spacing[4]} ${spacing[5]}`,
      borderRadius: radius.md,
    }}>
      {/* Tool type label */}
      <p style={{ margin: `0 0 ${spacing[1]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: "rgba(245,158,11,0.7)", textTransform: "uppercase",
        letterSpacing: "0.06em" }}>
        {isPromotion ? "AUTONOMY UPGRADE" : toolLabel}
      </p>

      {/* Summary */}
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.sm,
        color: colors.primary, lineHeight: typography.lineHeight.relaxed }}>
        {draft.summary}
      </p>

      {error && (
        <p style={{ margin: `0 0 ${spacing[2]}`, fontSize: typography.size.xs,
          color: "#ef4444", fontFamily: "monospace" }}>{error}</p>
      )}

      {editing ? (
        <div style={{ marginBottom: spacing[3] }}>
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            rows={3}
            style={{
              width: "100%", boxSizing: "border-box",
              background: colors.elevated, border: `1px solid ${colors.border}`,
              borderRadius: radius.sm, color: colors.primary,
              fontSize: typography.size.sm, padding: spacing[2],
              fontFamily: typography.fontFamily, resize: "vertical",
            }}
          />
          <div style={{ display: "flex", gap: spacing[2], marginTop: spacing[2] }}>
            <button className="btn-ghost" style={{ fontSize: 12, padding: "6px 14px" }}
              onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}
              onClick={async () => {
                try {
                  const parsed = JSON.parse(editText);
                  await api.drafts.edit(draft.id, parsed);
                  setEditing(false); onRefresh();
                } catch { setError("invalid json"); }
              }}>Save</button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", gap: spacing[2], flexWrap: "wrap" }}>
          <button
            className="btn-primary"
            disabled={!!loading}
            onClick={() => handle("confirm")}
            style={{ fontSize: 12, padding: "6px 16px" }}
          >
            {loading === "confirm" ? "…" : (isPromotion ? "Enable" : "Confirm")}
          </button>
          {!isPromotion && (
            <button
              className="btn-ghost"
              disabled={!!loading}
              onClick={() => {
                try { setEditText(JSON.stringify(JSON.parse(draft.tool_args_json), null, 2)); }
                catch { setEditText(draft.tool_args_json); }
                setEditing(true);
              }}
              style={{ fontSize: 12, padding: "6px 14px" }}
            >
              Edit
            </button>
          )}
          <button
            className="btn-ghost"
            disabled={!!loading}
            onClick={() => handle("dismiss")}
            style={{ fontSize: 12, padding: "6px 14px", color: colors.muted }}
          >
            {loading === "dismiss" ? "…" : "Dismiss"}
          </button>
        </div>
      )}

      <p style={{ margin: `${spacing[3]} 0 0`, fontSize: 10, color: colors.muted,
        fontFamily: "monospace" }}>
        {new Date(draft.created_at).toLocaleString()}
      </p>
    </div>
  );
}
