import { api } from "../api";
import { colors, typography, spacing, surfaces, radius } from "../design-system";

interface Campaign {
  id: string;
  intent: string;
  summary: string | null;
  status: string;
  expires_at: string | null;
  created_at: string;
}

interface Props {
  campaigns: Campaign[];
  onRefresh: () => void;
}

export default function CampaignCard({ campaigns, onRefresh }: Props) {
  if (!campaigns.length) return null;

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        VELLO IS WORKING ON
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[2] }}>
        {campaigns.map((c) => (
          <div key={c.id} style={{
            ...surfaces.panel,
            padding: `${spacing[3]} ${spacing[4]}`,
            borderRadius: radius.md,
            display: "flex", alignItems: "center", justifyContent: "space-between",
            gap: spacing[3],
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, fontSize: typography.size.sm, color: colors.primary,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {c.intent.replace(/_/g, " ")}
              </p>
              {c.summary && (
                <p style={{ margin: `${spacing[1]} 0 0`, fontSize: typography.size.xs,
                  color: colors.muted, overflow: "hidden", textOverflow: "ellipsis",
                  whiteSpace: "nowrap" }}>
                  {c.summary}
                </p>
              )}
            </div>
            <button
              className="btn-ghost"
              style={{ fontSize: 11, padding: "4px 10px", flexShrink: 0, color: colors.muted }}
              onClick={async () => {
                await api.agent.closeCampaign(c.id).catch(() => {});
                onRefresh();
              }}
            >
              Cancel
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
