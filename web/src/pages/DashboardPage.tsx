import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Nav from "../components/Nav";
import { useAuth } from "../App";
import { api } from "../api";
import type { BehavioralGap, PendingInference, SignalTrigger, TemporalDeviation } from "../types";
import { V } from "../vello-tokens";

function Mono({ children, size = 10, color, style }: {
  children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties;
}) {
  return (
    <span style={{ fontFamily: V.mono, fontSize: size, color: color || V.inkDim, letterSpacing: "0.04em", ...style }}>
      {children}
    </span>
  );
}

function Dot({ color = V.amber, size = 6 }: { color?: string; size?: number }) {
  return (
    <span style={{
      width: size, height: size, borderRadius: "50%", background: color,
      display: "inline-block", boxShadow: `0 0 ${size * 2}px ${color}`,
      animation: "velloDot 2.4s ease-in-out infinite", flexShrink: 0,
    }} />
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <Mono size={10} color={V.inkFaint} style={{ letterSpacing: "0.2em", textTransform: "uppercase", display: "block", marginBottom: 12 }}>
      {children}
    </Mono>
  );
}

function DeviationCard({ dev }: { dev: TemporalDeviation }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 18,
      padding: "16px 20px", borderRadius: 12,
      background: V.surface, border: `1px solid ${V.amberSoft}`,
      borderLeft: `2px solid ${V.amber}`,
    }}>
      <div style={{
        width: 34, height: 34, borderRadius: "50%",
        display: "grid", placeItems: "center",
        background: V.amberMist, border: `1px solid ${V.amberSoft}`,
        color: V.amber, fontSize: 16, flexShrink: 0,
      }}>◷</div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: "0 0 3px", fontSize: 15, color: V.ink, fontFamily: V.sans }}>{dev.message}</p>
        <Mono size={10} color={V.inkFaint}>
          +{dev.late_by_minutes} min late · usually {dev.expected_time}
        </Mono>
      </div>
    </div>
  );
}

function GapCard({ gap }: { gap: BehavioralGap }) {
  return (
    <div style={{
      padding: "14px 18px", borderRadius: 12,
      background: V.amberMist, border: `1px solid ${V.amberSoft}`,
      display: "flex", gap: 12, alignItems: "flex-start",
    }}>
      <span style={{ color: V.amber, fontSize: 13, marginTop: 2, flexShrink: 0 }}>◎</span>
      <div>
        <Mono size={10} color={V.amber} style={{ letterSpacing: "0.16em", textTransform: "uppercase", display: "block", marginBottom: 4 }}>
          {gap.domain} · {gap.type.replace(/_/g, " ")}
        </Mono>
        <p style={{ margin: 0, fontSize: 14, color: V.ink, lineHeight: 1.5, fontFamily: V.sans }}>{gap.description}</p>
      </div>
    </div>
  );
}

function SignalCard({ signal, onConfirm, onDismiss }: {
  signal: SignalTrigger; onConfirm: () => void; onDismiss: () => void;
}) {
  const priorityColor: Record<string, string> = { high: V.amber, medium: V.amber, low: V.inkDim };
  return (
    <div style={{
      padding: "16px 20px", borderRadius: 12,
      background: V.surface, border: `1px solid ${V.border}`,
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <Dot color={priorityColor[signal.priority] ?? V.inkDim} size={6} />
          <Mono size={10} style={{ letterSpacing: "0.16em", textTransform: "uppercase", color: V.inkDim }}>{signal.label}</Mono>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: V.ink, lineHeight: 1.5, fontFamily: V.sans }}>{signal.trigger_message}</p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <ActionBtn onClick={onConfirm}>yes</ActionBtn>
        <GhostBtn onClick={onDismiss}>later</GhostBtn>
      </div>
    </div>
  );
}

function InferenceCard({ inf, onConfirm, onDismiss }: {
  inf: PendingInference; onConfirm: () => void; onDismiss: () => void;
}) {
  return (
    <div style={{
      padding: "16px 20px", borderRadius: 12,
      background: V.surface,
      border: `1px solid ${V.border}`,
      borderTop: `1px solid ${V.obsSoft}`,
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <Dot color={V.obs} size={6} />
          <Mono size={10} color={V.obs} style={{ letterSpacing: "0.16em", textTransform: "uppercase" }}>vello noticed</Mono>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: V.ink, lineHeight: 1.5, fontFamily: V.serif, fontStyle: "italic" }}>{inf.description}</p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <ActionBtn onClick={onConfirm}>looks right</ActionBtn>
        <GhostBtn onClick={onDismiss}>no</GhostBtn>
      </div>
    </div>
  );
}

function ActionBtn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.sans, fontSize: 12, fontWeight: 600,
        color: "#100c06", background: V.ink,
        border: "none", borderRadius: 999, padding: "6px 14px",
        cursor: "pointer",
        boxShadow: hover ? "0 4px 16px rgba(245,158,11,0.2)" : "none",
        transition: "box-shadow .2s",
      }}>{children}</button>
  );
}

function GhostBtn({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.sans, fontSize: 12, fontWeight: 500,
        color: V.ink, background: "transparent",
        border: `1px solid ${hover ? V.borderHi : V.border}`,
        borderRadius: 999, padding: "5px 12px",
        cursor: "pointer", transition: "border-color .2s",
      }}>{children}</button>
  );
}

function QuickCard({ to, icon, title, desc }: { to: string; icon: string; title: string; desc: string }) {
  const [hover, setHover] = useState(false);
  return (
    <Link to={to} style={{ textDecoration: "none" }}>
      <div
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={{
          background: hover ? V.surfaceHi : V.surface,
          border: `1px solid ${hover ? V.borderHi : V.border}`,
          borderRadius: 14, padding: "20px 22px",
          transition: "background .2s, border-color .2s", cursor: "pointer",
        }}>
        <p style={{ margin: "0 0 10px", fontSize: 20, color: V.amber }}>{icon}</p>
        <p style={{ margin: "0 0 4px", fontFamily: V.serif, fontSize: 17, color: V.ink }}>{title}</p>
        <p style={{ margin: 0, fontFamily: V.sans, fontSize: 13, color: V.inkDim, lineHeight: 1.45 }}>{desc}</p>
      </div>
    </Link>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [inferences, setInferences] = useState<PendingInference[]>([]);
  const [signals, setSignals]       = useState<SignalTrigger[]>([]);
  const [deviations, setDeviations] = useState<TemporalDeviation[]>([]);
  const [gaps, setGaps]             = useState<BehavioralGap[]>([]);

  useEffect(() => {
    api.inferences.list().then(r => setInferences(r as PendingInference[])).catch(() => {});
    api.signals.list().then(setSignals).catch(() => {});
    api.temporal.deviations().then(setDeviations).catch(() => {});
    api.gaps.list().then(g => setGaps(g as BehavioralGap[])).catch(() => {});
  }, []);

  async function confirmInference(id: string) {
    await api.inferences.confirm(id).catch(() => {});
    setInferences(p => p.filter(i => i.id !== id));
  }
  async function dismissInference(id: string) {
    await api.inferences.dismiss(id).catch(() => {});
    setInferences(p => p.filter(i => i.id !== id));
  }
  async function confirmSignal(id: string) {
    await api.signals.confirm(id).catch(() => {});
    setSignals(p => p.filter(s => s.id !== id));
  }
  async function dismissSignal(id: string) {
    await api.signals.dismiss(id).catch(() => {});
    setSignals(p => p.filter(s => s.id !== id));
  }

  const hour     = new Date().getHours();
  const greeting = hour < 12 ? "good morning" : hour < 17 ? "good afternoon" : "good evening";
  const dateStr  = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const hasAlerts = deviations.length + gaps.length + signals.length + inferences.length > 0;
  const totalItems = deviations.length + gaps.length + signals.length + inferences.length;

  return (
    <div style={{ minHeight: "100vh", background: V.bg, display: "flex", flexDirection: "column" }}>
      <Nav />
      <div style={{ maxWidth: 720, margin: "0 auto", padding: "52px 24px", width: "100%" }}>

        {/* Greeting */}
        <div style={{ marginBottom: hasAlerts ? 48 : 64 }}>
          <Mono size={10} color={V.inkFaint} style={{ letterSpacing: "0.2em", textTransform: "uppercase", display: "block", marginBottom: 14 }}>
            {dateStr.toUpperCase()}
          </Mono>
          <h1 style={{
            margin: "0 0 10px", fontFamily: V.serif, fontWeight: 400,
            fontSize: "clamp(40px, 5vw, 60px)", letterSpacing: "-0.02em", lineHeight: 1, color: V.ink,
          }}>
            {greeting}{user?.email ? `, ${user.email.split("@")[0]}` : ""}.
          </h1>
          <p style={{ margin: 0, fontFamily: V.serif, fontStyle: "italic", fontSize: 16, color: V.inkDim }}>
            {totalItems > 0
              ? `${totalItems} thing${totalItems !== 1 ? "s" : ""} to know.`
              : "nothing to surface right now."}
          </p>
        </div>

        {/* Temporal deviations */}
        {deviations.length > 0 && (
          <section style={{ marginBottom: 32 }}>
            <SectionLabel>running late</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {deviations.map(d => <DeviationCard key={d.pattern_key} dev={d} />)}
            </div>
          </section>
        )}

        {/* Behavioral gaps */}
        {gaps.length > 0 && (
          <section style={{ marginBottom: 32 }}>
            <SectionLabel>patterns vello noticed</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {gaps.map((g, i) => <GapCard key={i} gap={g} />)}
            </div>
          </section>
        )}

        {/* Signal triggers */}
        {signals.length > 0 && (
          <section style={{ marginBottom: 32 }}>
            <SectionLabel>vello detected</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {signals.map(s => (
                <SignalCard key={s.id} signal={s}
                  onConfirm={() => confirmSignal(s.id)}
                  onDismiss={() => dismissSignal(s.id)} />
              ))}
            </div>
          </section>
        )}

        {/* Pending inferences */}
        {inferences.length > 0 && (
          <section style={{ marginBottom: 40 }}>
            <SectionLabel>confirm what vello learned</SectionLabel>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {inferences.map(inf => (
                <InferenceCard key={inf.id} inf={inf}
                  onConfirm={() => confirmInference(inf.id)}
                  onDismiss={() => dismissInference(inf.id)} />
              ))}
            </div>
          </section>
        )}

        {/* Divider */}
        <div style={{ height: 1, background: V.hairline, margin: "0 0 40px" }} />

        {/* Quick access */}
        <section style={{ marginBottom: 40 }}>
          <SectionLabel>quick access</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <QuickCard to="/dialogue" icon="◎" title="Dialogue"    desc="Talk to Vello. Build your profile through conversation." />
            <QuickCard to="/profile"  icon="◈" title="Life Context" desc="View and edit what Vello knows about you." />
            <QuickCard to="/routines" icon="◇" title="Routines"     desc="Manage your daily and weekly routines." />
            <QuickCard to="/settings" icon="○" title="Settings"     desc="Connect Kortex and configure Vello." />
          </div>
        </section>

        {/* Onboarding nudge */}
        {!user?.onboarding_complete && (
          <div style={{
            padding: "20px 24px", borderRadius: 14,
            background: V.amberMist, border: `1px solid ${V.amberSoft}`,
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
          }}>
            <div>
              <p style={{ margin: "0 0 4px", fontFamily: V.serif, fontSize: 17, color: V.ink }}>
                introduce yourself to vello
              </p>
              <p style={{ margin: 0, fontFamily: V.sans, fontSize: 13, color: V.inkDim, lineHeight: 1.5 }}>
                a short conversation gets you up and running. vello learns the rest over time.
              </p>
            </div>
            <Link to="/dialogue" style={{ textDecoration: "none" }}>
              <ActionBtn onClick={() => {}}>get started →</ActionBtn>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
