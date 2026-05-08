import { api } from "../api";
import { colors, typography, spacing, surfaces, radius } from "../design-system";

interface Playbook { id: string; slug: string; title: string; source: string; enabled: number; }

interface Props {
  playbooks: Playbook[];
  onRefresh: () => void;
}

export default function PlaybookProposal({ playbooks, onRefresh }: Props) {
  const proposals = playbooks.filter((p) => p.source === "learned" && !p.enabled);
  if (!proposals.length) return null;

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        PATTERN DETECTED
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[2] }}>
        {proposals.map((pb) => (
          <div key={pb.id} style={{
            ...surfaces.panel,
            borderLeft: `2px solid ${colors.border}`,
            padding: `${spacing[3]} ${spacing[4]}`,
            borderRadius: radius.md,
          }}>
            <p style={{ margin: `0 0 ${spacing[2]}`, fontSize: typography.size.sm, color: colors.primary }}>
              {pb.title}
            </p>
            <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs, color: colors.muted }}>
              Vello noticed you do this regularly. Make it a playbook?
            </p>
            <div style={{ display: "flex", gap: spacing[2] }}>
              <button className="btn-primary" style={{ fontSize: 12, padding: "5px 14px" }}
                onClick={async () => {
                  await api.playbooks.acceptLearned(pb.id).catch(() => {});
                  onRefresh();
                }}>
                Yes, save it
              </button>
              <button className="btn-ghost" style={{ fontSize: 12, padding: "5px 12px", color: colors.muted }}
                onClick={async () => {
                  await api.playbooks.disable(pb.id).catch(() => {});
                  onRefresh();
                }}>
                Dismiss
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
