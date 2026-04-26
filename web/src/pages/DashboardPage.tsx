import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Nav from "../components/Nav";
import { useAuth } from "../App";
import { api } from "../api";
import type { BehavioralGap, PendingInference, SignalTrigger, TemporalDeviation } from "../types";
import { colors, typography, radius, surfaces } from "../design-system";

function InferenceCard({ inf, onConfirm, onDismiss }: {
  inf: PendingInference;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  return (
    <div style={{
      ...surfaces.signal,
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
    }}>
      <div>
        <p style={{ margin: "0 0 4px", fontSize: typography.size.xs, color: colors.muted, letterSpacing: "0.1em", fontWeight: typography.weight.bold }}>VELLO NOTICED</p>
        <p style={{ margin: 0, fontSize: typography.size.md, color: colors.primary, lineHeight: typography.lineHeight.normal }}>{inf.description}</p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={onConfirm} className="btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}>Looks right</button>
        <button onClick={onDismiss} className="btn-ghost"   style={{ fontSize: 12, padding: "5px 12px" }}>No</button>
      </div>
    </div>
  );
}

const PRIORITY_DOT: Record<string, string> = {
  high:   colors.error,
  medium: colors.warning,
  low:    colors.muted,
};

function SignalCard({ signal, onConfirm, onDismiss }: {
  signal: SignalTrigger;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  return (
    <div style={{
      ...surfaces.signal,
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{
            width: 7, height: 7, borderRadius: "50%",
            background: PRIORITY_DOT[signal.priority] ?? colors.muted,
            flexShrink: 0, display: "inline-block",
          }} />
          <p style={{ margin: 0, fontSize: typography.size.xs, color: colors.muted, letterSpacing: "0.1em", fontWeight: typography.weight.bold }}>
            {signal.label.toUpperCase()}
          </p>
        </div>
        <p style={{ margin: 0, fontSize: typography.size.md, color: colors.primary, lineHeight: typography.lineHeight.normal }}>
          {signal.trigger_message}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={onConfirm} className="btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}>Yes</button>
        <button onClick={onDismiss} className="btn-ghost"   style={{ fontSize: 12, padding: "5px 12px" }}>Later</button>
      </div>
    </div>
  );
}

function DeviationCard({ dev }: { dev: TemporalDeviation }) {
  return (
    <div style={{
      background: colors.surface, border: "1px solid rgba(245,158,11,0.2)",
      borderRadius: radius.md, padding: "14px 20px",
      display: "flex", alignItems: "center", gap: 16,
    }}>
      <span style={{ fontSize: 18, flexShrink: 0, color: colors.warning }}>◷</span>
      <div>
        <p style={{ margin: "0 0 2px", fontSize: typography.size.base, fontWeight: typography.weight.semibold, color: colors.primary }}>{dev.message}</p>
        <p style={{ margin: 0, fontSize: typography.size.xs, color: colors.muted }}>
          {dev.late_by_minutes} min late · usually {dev.expected_time}
        </p>
      </div>
    </div>
  );
}

function GapCard({ gap }: { gap: BehavioralGap }) {
  return (
    <div style={{ ...surfaces.gap, display: "flex", alignItems: "flex-start", gap: 12 }}>
      <span style={{ fontSize: 14, flexShrink: 0, color: colors.warning, marginTop: 1 }}>◎</span>
      <div>
        <p style={{ margin: "0 0 3px", fontSize: typography.size.xs, color: colors.warning, fontWeight: typography.weight.bold, letterSpacing: "0.08em" }}>
          {gap.domain.toUpperCase()} · {gap.type.replace(/_/g, " ").toUpperCase()}
        </p>
        <p style={{ margin: 0, fontSize: typography.size.md, color: colors.primary, lineHeight: typography.lineHeight.normal }}>
          {gap.description}
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [inferences, setInferences] = useState<PendingInference[]>([]);
  const [signals, setSignals]       = useState<SignalTrigger[]>([]);
  const [deviations, setDeviations] = useState<TemporalDeviation[]>([]);
  const [gaps, setGaps]             = useState<BehavioralGap[]>([]);

  useEffect(() => {
    api.inferences.list().then((r) => setInferences(r as PendingInference[])).catch(() => {});
    api.signals.list().then(setSignals).catch(() => {});
    api.temporal.deviations().then(setDeviations).catch(() => {});
    api.gaps.list().then((g) => setGaps(g as BehavioralGap[])).catch(() => {});
  }, []);

  async function confirmInference(id: string) {
    await api.inferences.confirm(id).catch(() => {});
    setInferences((p) => p.filter((i) => i.id !== id));
  }

  async function dismissInference(id: string) {
    await api.inferences.dismiss(id).catch(() => {});
    setInferences((p) => p.filter((i) => i.id !== id));
  }

  async function confirmSignal(id: string) {
    await api.signals.confirm(id).catch(() => {});
    setSignals((p) => p.filter((s) => s.id !== id));
  }

  async function dismissSignal(id: string) {
    await api.signals.dismiss(id).catch(() => {});
    setSignals((p) => p.filter((s) => s.id !== id));
  }

  const hour     = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const hasAlerts = deviations.length > 0 || gaps.length > 0 || signals.length > 0 || inferences.length > 0;

  return (
    <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", width: "100%" }}>

        {/* Greeting */}
        <div style={{ marginBottom: hasAlerts ? 36 : 48 }}>
          <p style={{ margin: "0 0 6px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.12em" }}>
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }).toUpperCase()}
          </p>
          <h1 style={{ margin: 0, fontSize: typography.size["3xl"], fontWeight: typography.weight.extrabold, color: colors.white, letterSpacing: "-0.03em" }}>
            {greeting}.
          </h1>
        </div>

        {/* Temporal deviations */}
        {deviations.length > 0 && (
          <section style={{ marginBottom: 28 }}>
            <p style={{ margin: "0 0 12px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.1em" }}>
              RUNNING LATE
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {deviations.map((d) => <DeviationCard key={d.pattern_key} dev={d} />)}
            </div>
          </section>
        )}

        {/* Behavioral gaps */}
        {gaps.length > 0 && (
          <section style={{ marginBottom: 28 }}>
            <p style={{ margin: "0 0 12px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.1em" }}>
              PATTERNS VELLO NOTICED
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {gaps.map((g, i) => <GapCard key={i} gap={g} />)}
            </div>
          </section>
        )}

        {/* Signal triggers */}
        {signals.length > 0 && (
          <section style={{ marginBottom: 28 }}>
            <p style={{ margin: "0 0 12px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.1em" }}>
              VELLO DETECTED
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {signals.map((s) => (
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
            <p style={{ margin: "0 0 16px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.1em" }}>
              CONFIRM WHAT VELLO LEARNED
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {inferences.map((inf) => (
                <InferenceCard key={inf.id} inf={inf}
                  onConfirm={() => confirmInference(inf.id)}
                  onDismiss={() => dismissInference(inf.id)} />
              ))}
            </div>
          </section>
        )}

        {/* Quick access */}
        <section style={{ marginBottom: 40 }}>
          <p style={{ margin: "0 0 16px", fontSize: typography.size.xs, color: colors.muted, fontWeight: typography.weight.bold, letterSpacing: "0.1em" }}>QUICK ACCESS</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { to: "/dialogue", icon: "◎", title: "Talk to Vello",  desc: "Build your profile through conversation" },
              { to: "/profile",  icon: "◈", title: "Life Context",   desc: "View and edit what Vello knows about you" },
              { to: "/routines", icon: "◇", title: "Routines",       desc: "Manage your daily and weekly routines" },
              { to: "/settings", icon: "○", title: "Settings",       desc: "Connect Kortex and configure Vello" },
            ].map(({ to, icon, title, desc }) => (
              <Link key={to} to={to} style={{ textDecoration: "none" }}>
                <div style={{
                  background: colors.surface, border: `1px solid ${colors.border}`,
                  borderRadius: radius.lg, padding: "20px 22px",
                  transition: "border-color 0.15s, background 0.15s", cursor: "pointer",
                }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = colors.borderHover;
                    (e.currentTarget as HTMLElement).style.background  = colors.surfaceHover;
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = colors.border;
                    (e.currentTarget as HTMLElement).style.background  = colors.surface;
                  }}
                >
                  <p style={{ margin: "0 0 8px", fontSize: 18, color: colors.white }}>{icon}</p>
                  <p style={{ margin: "0 0 4px", fontSize: typography.size.md, fontWeight: typography.weight.semibold, color: colors.primary }}>{title}</p>
                  <p style={{ margin: 0, fontSize: typography.size.sm, color: colors.muted, lineHeight: typography.lineHeight.normal }}>{desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Onboarding nudge */}
        {!user?.onboarding_complete && (
          <div style={{
            ...surfaces.panel,
            border: "1px solid rgba(255,255,255,0.12)",
            padding: "20px 24px",
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
          }}>
            <div>
              <p style={{ margin: "0 0 4px", fontSize: typography.size.md, fontWeight: typography.weight.semibold, color: colors.primary }}>
                Introduce yourself to Vello
              </p>
              <p style={{ margin: 0, fontSize: typography.size.base, color: colors.muted, lineHeight: typography.lineHeight.normal }}>
                A quick three-question conversation gets you up and running. Vello learns the rest over time.
              </p>
            </div>
            <Link to="/dialogue">
              <button className="btn-primary" style={{ fontSize: 13, whiteSpace: "nowrap" }}>
                Get started →
              </button>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
