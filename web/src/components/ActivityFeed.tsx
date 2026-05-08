import { colors, typography, spacing, surfaces, radius } from "../design-system";

interface Session {
  id: string;
  trigger_kind: string;
  outcome: string;
  steps: number;
  started_at: string;
  ended_at: string | null;
}

interface Props {
  sessions: Session[];
}

const OUTCOME_LABELS: Record<string, string> = {
  success:   "✓",
  drafted:   "·",
  need_info: "?",
  deferred:  "→",
  max_steps: "‼",
  error:     "✗",
  suppressed: "–",
};

export default function ActivityFeed({ sessions }: Props) {
  if (!sessions.length) return null;
  const recent = sessions.slice(0, 10);

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        VELLO DID
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[1] }}>
        {recent.map((s) => (
          <div key={s.id} style={{
            ...surfaces.panel,
            padding: `${spacing[2]} ${spacing[4]}`,
            borderRadius: radius.md,
            display: "flex", alignItems: "center", gap: spacing[3],
          }}>
            <span style={{ fontFamily: "monospace", fontSize: typography.size.xs,
              color: s.outcome === "error" ? "#ef4444"
                   : s.outcome === "drafted" ? "rgba(245,158,11,0.7)"
                   : colors.muted,
              flexShrink: 0, width: 14, textAlign: "center" }}>
              {OUTCOME_LABELS[s.outcome] || "·"}
            </span>
            <span style={{ fontSize: typography.size.sm, color: colors.primary, flex: 1 }}>
              {s.trigger_kind.replace(/_/g, " ")}
            </span>
            <span style={{ fontSize: 10, color: colors.muted, fontFamily: "monospace",
              flexShrink: 0 }}>
              {new Date(s.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
