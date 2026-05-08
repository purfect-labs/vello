import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../App";
import Nav from "../components/Nav";
import DraftsInbox from "../components/DraftsInbox";
import CampaignCard from "../components/CampaignCard";
import ListsPanel from "../components/ListsPanel";
import InventoryPanel from "../components/InventoryPanel";
import ActivityFeed from "../components/ActivityFeed";
import PlaybookProposal from "../components/PlaybookProposal";
import PromotionPrompt from "../components/PromotionPrompt";
import { useVoice } from "../hooks/useVoice";
import { usePush } from "../hooks/usePush";
import { colors, typography, spacing } from "../design-system";

type Draft = { id: string; tool_name: string; summary: string; status: string; tool_args_json: string; created_at: string; };
type Campaign = { id: string; intent: string; summary: string | null; status: string; expires_at: string | null; created_at: string; };
type HomeList = { id: string; slug: string; label: string; kind: string; items: Array<{ id: string; label: string; qty: string | null; status: string }>; };
type InventoryItem = { id: string; label: string; last_used_at: string | null; est_lifetime_days: number | null; low_threshold_days: number | null; };
type Session = { id: string; trigger_kind: string; outcome: string; steps: number; started_at: string; ended_at: string | null; };
type Playbook = { id: string; slug: string; title: string; source: string; enabled: number; };

export default function HomePage() {
  const { user } = useAuth();
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [lists, setLists] = useState<HomeList[]>([]);
  const [lowStock, setLowStock] = useState<InventoryItem[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [loading, setLoading] = useState(true);
  const voiceInputRef = useRef<((t: string) => void) | null>(null);
  const voice = useVoice({
    autoSpeak: false,
    onFinalResult: (transcript) => {
      if (voiceInputRef.current) voiceInputRef.current(transcript);
    },
  });
  const push = usePush();

  const load = useCallback(async () => {
    try {
      const [d, c, l, inv, s, pb] = await Promise.allSettled([
        api.drafts.list("pending"),
        api.agent.campaigns(),
        api.lists.getAll(),
        api.inventory.list(true),
        api.agent.sessions(15),
        api.playbooks.list(),
      ]);
      if (d.status === "fulfilled") setDrafts(d.value as Draft[]);
      if (c.status === "fulfilled") setCampaigns(c.value as Campaign[]);
      if (l.status === "fulfilled") setLists(l.value as HomeList[]);
      if (inv.status === "fulfilled") setLowStock(inv.value as InventoryItem[]);
      if (s.status === "fulfilled") setSessions(s.value as Session[]);
      if (pb.status === "fulfilled") setPlaybooks(pb.value as Playbook[]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  };

  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

  // Separate promotion prompts from regular drafts so they render in own section
  const regularDrafts = drafts.filter((d) => d.tool_name !== "__promotion__");
  const promotionDrafts = drafts.filter((d) => d.tool_name === "__promotion__");

  return (
    <div style={{ minHeight: "100vh", background: colors.bg }}>
      <Nav />
      <div style={{ maxWidth: 680, margin: "0 auto", padding: `${spacing[10]} ${spacing[5]}` }}>
        {/* Header */}
        <div style={{ marginBottom: spacing[10] }}>
          <p style={{ margin: `0 0 ${spacing[1]}`, fontSize: typography.size.xs,
            fontFamily: "monospace", color: colors.muted, textTransform: "uppercase",
            letterSpacing: "0.08em" }}>
            {today}
          </p>
          <h1 style={{ margin: 0, fontSize: typography.size["2xl"], fontWeight: typography.weight.normal,
            color: colors.primary, letterSpacing: "-0.02em" }}>
            {greeting()}{user?.email ? `, ${user.email.split("@")[0]}` : ""}.
          </h1>
        </div>

        {loading ? (
          <p style={{ color: colors.muted, fontSize: typography.size.sm }}>Loading…</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: spacing[9] }}>

            {/* Promotion prompts (trust updates) */}
            <PromotionPrompt drafts={promotionDrafts} onRefresh={load} />

            {/* Open campaigns */}
            <CampaignCard campaigns={campaigns} onRefresh={load} />

            {/* Drafts inbox */}
            <DraftsInbox drafts={regularDrafts} onRefresh={load} />

            {/* Inventory low-stock */}
            <InventoryPanel items={lowStock} onRefresh={load} />

            {/* Household lists */}
            <ListsPanel lists={lists} onRefresh={load} />

            {/* Playbook proposals */}
            <PlaybookProposal playbooks={playbooks} onRefresh={load} />

            {/* Push nudge — shown once until subscribed */}
            {push.supported && push.permission === "default" && !push.subscribed && (
              <div style={{ display: "flex", alignItems: "center", gap: spacing[3],
                padding: `${spacing[2]} ${spacing[4]}`,
                border: `1px solid ${colors.border}`, borderRadius: 8 }}>
                <span style={{ fontSize: typography.size.xs, color: colors.muted, flex: 1 }}>
                  Get push notifications when Vello wants to act.
                </span>
                <button className="btn-ghost"
                  style={{ fontSize: 11, padding: "4px 12px" }}
                  onClick={() => push.subscribe()}>
                  {push.loading ? "…" : "Enable"}
                </button>
              </div>
            )}

            {/* Ask Vello inline trigger */}
            <AskVelloBar
              voiceInputRef={voiceInputRef}
              onTrigger={async (text) => {
                setTriggering(true);
                try {
                  const result = await api.agent.trigger("user_request", { message: text });
                  if (result.finish_message && voice.isSupported) {
                    voice.speak(result.finish_message);
                  }
                  await load();
                } finally { setTriggering(false); }
              }}
              triggering={triggering}
              voice={voice}
            />

            {/* Activity feed */}
            <ActivityFeed sessions={sessions} />
          </div>
        )}
      </div>
    </div>
  );
}

function AskVelloBar({
  onTrigger, triggering, voice, voiceInputRef,
}: {
  onTrigger: (text: string) => void;
  triggering: boolean;
  voice: ReturnType<typeof useVoice>;
  voiceInputRef: React.MutableRefObject<((t: string) => void) | null>;
}) {
  const [text, setText] = useState("");

  // Register this component's setText with the ref so the voice hook can populate it
  useEffect(() => {
    voiceInputRef.current = (t: string) => setText(t);
    return () => { voiceInputRef.current = null; };
  }, [voiceInputRef]);

  function submit() {
    const t = text.trim();
    if (!t || triggering) return;
    setText("");
    onTrigger(t);
  }

  // Mic: hold-to-talk
  function handleMicDown() {
    if (!voice.isSupported || triggering) return;
    voice.startListening();
  }
  function handleMicUp() {
    if (!voice.listening) return;
    voice.stopListening();
    // The voice hook fires onFinalResult — for push-to-talk we capture interim
    // transcript via a ref in a real implementation. Here we use what's in `text`
    // if it was populated via the onResult callback.
  }

  return (
    <div style={{ display: "flex", gap: spacing[2], alignItems: "center" }}>
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
        placeholder="Tell Vello to do something…"
        disabled={triggering}
        style={{
          flex: 1, background: "transparent",
          border: `1px solid ${colors.border}`, borderRadius: 6,
          color: colors.primary, fontSize: typography.size.sm,
          padding: `${spacing[2]} ${spacing[3]}`, outline: "none",
        }}
      />
      {voice.isSupported && (
        <button
          onPointerDown={handleMicDown}
          onPointerUp={handleMicUp}
          onPointerLeave={handleMicUp}
          disabled={triggering}
          style={{
            flexShrink: 0, width: 36, height: 36, borderRadius: "50%",
            border: `1px solid ${voice.listening ? "rgba(245,158,11,0.6)" : colors.border}`,
            background: voice.listening ? "rgba(245,158,11,0.1)" : "transparent",
            cursor: "pointer", transition: "border-color 0.15s, background 0.15s",
            display: "flex", alignItems: "center", justifyContent: "center",
            color: voice.listening ? "rgba(245,158,11,0.9)" : colors.muted,
            fontSize: 16,
          }}
          title="Hold to speak"
        >
          {voice.state === "speaking" ? "▶" : voice.listening ? "●" : "🎙"}
        </button>
      )}
      <button
        className="btn-primary"
        onClick={submit}
        disabled={!text.trim() || triggering}
        style={{ fontSize: 13, padding: "8px 18px", flexShrink: 0 }}
      >
        {triggering ? "…" : "Go"}
      </button>
    </div>
  );
}
