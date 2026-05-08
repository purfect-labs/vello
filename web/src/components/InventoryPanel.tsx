import { api } from "../api";
import { colors, typography, spacing, surfaces, radius } from "../design-system";

interface InventoryItem {
  id: string;
  label: string;
  last_used_at: string | null;
  est_lifetime_days: number | null;
  low_threshold_days: number | null;
}

interface Props {
  items: InventoryItem[];
  onRefresh: () => void;
}

export default function InventoryPanel({ items, onRefresh }: Props) {
  if (!items.length) return null;

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        RUNNING LOW
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[1] }}>
        {items.map((item) => (
          <div key={item.id} style={{
            ...surfaces.panel,
            padding: `${spacing[2]} ${spacing[4]}`,
            borderRadius: radius.md,
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <span style={{ fontSize: typography.size.sm, color: colors.primary }}>
              {item.label}
            </span>
            <button
              className="btn-ghost"
              style={{ fontSize: 11, padding: "3px 10px" }}
              onClick={async () => {
                await api.inventory.action(item.id, "restocked").catch(() => {});
                onRefresh();
              }}
            >
              Restocked
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
