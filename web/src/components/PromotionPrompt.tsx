import { api } from "../api";
import { colors, typography, spacing, surfaces, radius } from "../design-system";

interface Draft { id: string; tool_name: string; summary: string; tool_args_json: string; status: string; }

interface Props {
  drafts: Draft[];
  onRefresh: () => void;
}

export default function PromotionPrompt({ drafts, onRefresh }: Props) {
  const promotions = drafts.filter(
    (d) => d.status === "pending" && d.tool_name === "__promotion__"
  );
  if (!promotions.length) return null;

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        TRUST UPDATE
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[2] }}>
        {promotions.map((d) => {
          let toolName = "";
          try { toolName = JSON.parse(d.tool_args_json).tool_name || ""; }
          catch { /* pass */ }

          return (
            <div key={d.id} style={{
              ...surfaces.panel,
              borderLeft: `2px solid ${colors.borderStrong}`,
              padding: `${spacing[3]} ${spacing[4]}`,
              borderRadius: radius.md,
            }}>
              <p style={{ margin: `0 0 ${spacing[2]}`, fontSize: typography.size.sm,
                color: colors.primary }}>
                {d.summary}
              </p>
              <div style={{ display: "flex", gap: spacing[2] }}>
                <button
                  className="btn-primary"
                  style={{ fontSize: 12, padding: "5px 14px" }}
                  onClick={async () => {
                    if (toolName) await api.agent.acceptPromotion(toolName).catch(() => {});
                    await api.drafts.confirm(d.id).catch(() => {});
                    onRefresh();
                  }}>
                  Enable automatic
                </button>
                <button
                  className="btn-ghost"
                  style={{ fontSize: 12, padding: "5px 12px", color: colors.muted }}
                  onClick={async () => {
                    await api.drafts.dismiss(d.id).catch(() => {});
                    onRefresh();
                  }}>
                  Keep drafting
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
