import { useState } from "react";
import { api } from "../api";
import { colors, typography, spacing, surfaces, radius } from "../design-system";

interface ListItem { id: string; label: string; qty: string | null; status: string; }
interface HomeList { id: string; slug: string; label: string; kind: string; items: ListItem[]; }

interface Props {
  lists: HomeList[];
  onRefresh: () => void;
}

export default function ListsPanel({ lists, onRefresh }: Props) {
  const [adding, setAdding] = useState<Record<string, string>>({});
  const [addQty, setAddQty] = useState<Record<string, string>>({});

  if (!lists.length) return null;
  const activeLists = lists.filter((l) => l.items.some((it) => it.status === "open"));
  if (!activeLists.length) return null;

  return (
    <section>
      <p style={{ margin: `0 0 ${spacing[3]}`, fontSize: typography.size.xs,
        fontFamily: "monospace", color: colors.muted, letterSpacing: "0.08em",
        textTransform: "uppercase" }}>
        LISTS
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: spacing[3] }}>
        {activeLists.map((list) => (
          <div key={list.id} style={{ ...surfaces.panel, padding: `${spacing[3]} ${spacing[4]}`, borderRadius: radius.md }}>
            <p style={{ margin: `0 0 ${spacing[2]}`, fontSize: typography.size.xs,
              fontFamily: "monospace", color: colors.muted, textTransform: "uppercase",
              letterSpacing: "0.06em" }}>
              {list.label}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: spacing[1] }}>
              {list.items.filter((it) => it.status === "open").map((item) => (
                <div key={item.id} style={{ display: "flex", alignItems: "center",
                  gap: spacing[2], padding: `${spacing[1]} 0` }}>
                  <button
                    onClick={async () => {
                      await api.lists.updateItem(list.id, item.id, "done").catch(() => {});
                      onRefresh();
                    }}
                    style={{ width: 14, height: 14, borderRadius: 3, flexShrink: 0,
                      border: `1px solid ${colors.border}`, background: "transparent",
                      cursor: "pointer", padding: 0 }}
                  />
                  <span style={{ fontSize: typography.size.sm, color: colors.primary, flex: 1 }}>
                    {item.label}{item.qty ? ` × ${item.qty}` : ""}
                  </span>
                </div>
              ))}
            </div>
            {/* Add item inline */}
            <div style={{ display: "flex", gap: spacing[2], marginTop: spacing[3] }}>
              <input
                value={adding[list.id] || ""}
                onChange={(e) => setAdding({ ...adding, [list.id]: e.target.value })}
                onKeyDown={async (e) => {
                  if (e.key === "Enter" && adding[list.id]?.trim()) {
                    await api.lists.addItem(list.id, { label: adding[list.id].trim(), qty: addQty[list.id] || undefined }).catch(() => {});
                    setAdding({ ...adding, [list.id]: "" });
                    setAddQty({ ...addQty, [list.id]: "" });
                    onRefresh();
                  }
                }}
                placeholder="Add item…"
                style={{ flex: 1, background: "transparent", border: "none", borderBottom: `1px solid ${colors.border}`,
                  color: colors.primary, fontSize: typography.size.sm, padding: "4px 0", outline: "none" }}
              />
              <input
                value={addQty[list.id] || ""}
                onChange={(e) => setAddQty({ ...addQty, [list.id]: e.target.value })}
                placeholder="qty"
                style={{ width: 40, background: "transparent", border: "none",
                  borderBottom: `1px solid ${colors.border}`, color: colors.muted,
                  fontSize: typography.size.xs, padding: "4px 0", outline: "none", textAlign: "center" }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
