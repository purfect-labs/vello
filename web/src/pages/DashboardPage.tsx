import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Nav from "../components/Nav";
import { useAuth } from "../App";
import { api } from "../api";
import type { PendingInference, SignalTrigger, TemporalDeviation } from "../types";

function InferenceCard({ inf, onConfirm, onDismiss }: {
  inf: PendingInference;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  return (
    <div style={{
      background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.1)",
      borderRadius: 14, padding: "16px 20px",
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
    }}>
      <div>
        <p style={{ margin: "0 0 4px", fontSize: 11, color: "#505050", letterSpacing: "0.1em", fontWeight: 700 }}>VELLO NOTICED</p>
        <p style={{ margin: 0, fontSize: 14, color: "#f5f5f5", lineHeight: 1.5 }}>{inf.description}</p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={onConfirm} className="btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}>
          Looks right
        </button>
        <button onClick={onDismiss} className="btn-ghost" style={{ fontSize: 12, padding: "5px 12px" }}>
          No
        </button>
      </div>
    </div>
  );
}

const PRIORITY_DOT: Record<string, string> = {
  high: "#ff4444",
  medium: "#ffaa00",
  low: "#888",
};

function SignalCard({ signal, onConfirm, onDismiss }: {
  signal: SignalTrigger;
  onConfirm: () => void;
  onDismiss: () => void;
}) {
  return (
    <div style={{
      background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.1)",
      borderRadius: 14, padding: "16px 20px",
      display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <span style={{
            width: 7, height: 7, borderRadius: "50%",
            background: PRIORITY_DOT[signal.priority] ?? "#888",
            flexShrink: 0, display: "inline-block",
          }} />
          <p style={{ margin: 0, fontSize: 11, color: "#505050", letterSpacing: "0.1em", fontWeight: 700 }}>
            {signal.label.toUpperCase()}
          </p>
        </div>
        <p style={{ margin: 0, fontSize: 14, color: "#f5f5f5", lineHeight: 1.5 }}>
          {signal.trigger_message}
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
        <button onClick={onConfirm} className="btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}>
          Yes
        </button>
        <button onClick={onDismiss} className="btn-ghost" style={{ fontSize: 12, padding: "5px 12px" }}>
          Later
        </button>
      </div>
    </div>
  );
}

function DeviationCard({ dev }: { dev: TemporalDeviation }) {
  return (
    <div style={{
      background: "#0a0a0a", border: "1px solid rgba(255,170,0,0.2)",
      borderRadius: 14, padding: "14px 20px",
      display: "flex", alignItems: "center", gap: 16,
    }}>
      <span style={{ fontSize: 18, flexShrink: 0 }}>◷</span>
      <div>
        <p style={{ margin: "0 0 2px", fontSize: 13, fontWeight: 600, color: "#f5f5f5" }}>{dev.message}</p>
        <p style={{ margin: 0, fontSize: 11, color: "#505050" }}>
          {dev.late_by_minutes} min late · usually {dev.expected_time}
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [inferences, setInferences]   = useState<PendingInference[]>([]);
  const [signals, setSignals]         = useState<SignalTrigger[]>([]);
  const [deviations, setDeviations]   = useState<TemporalDeviation[]>([]);

  useEffect(() => {
    api.inferences.list().then((r) => setInferences(r as PendingInference[])).catch(() => {});
    api.signals.list().then(setSignals).catch(() => {});
    api.temporal.deviations().then(setDeviations).catch(() => {});
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

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  const hasAlerts = deviations.length > 0 || signals.length > 0 || inferences.length > 0;

  return (
    <div style={{ minHeight: "100vh", background: "#000", display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 760, margin: "0 auto", padding: "48px 24px", width: "100%" }}>

        {/* Greeting */}
        <div style={{ marginBottom: hasAlerts ? 36 : 48 }}>
          <p style={{ margin: "0 0 6px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.12em" }}>
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" }).toUpperCase()}
          </p>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: "#fff", letterSpacing: "-0.03em" }}>
            {greeting}.
          </h1>
        </div>

        {/* Temporal deviations */}
        {deviations.length > 0 && (
          <section style={{ marginBottom: 28 }}>
            <p style={{ margin: "0 0 12px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.1em" }}>
              RUNNING LATE
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {deviations.map((d) => (
                <DeviationCard key={d.pattern_key} dev={d} />
              ))}
            </div>
          </section>
        )}

        {/* Signal triggers */}
        {signals.length > 0 && (
          <section style={{ marginBottom: 28 }}>
            <p style={{ margin: "0 0 12px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.1em" }}>
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
            <p style={{ margin: "0 0 16px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.1em" }}>
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

        {/* Quick actions */}
        <section style={{ marginBottom: 40 }}>
          <p style={{ margin: "0 0 16px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.1em" }}>QUICK ACCESS</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { to: "/dialogue", icon: "◎", title: "Talk to Vello", desc: "Build your profile through conversation" },
              { to: "/profile",  icon: "◈", title: "Life Context",   desc: "View and edit what Vello knows about you" },
              { to: "/routines", icon: "◇", title: "Routines",       desc: "Manage your daily and weekly routines" },
              { to: "/settings", icon: "○", title: "Settings",       desc: "Connect Kortex and configure Vello" },
            ].map(({ to, icon, title, desc }) => (
              <Link key={to} to={to} style={{ textDecoration: "none" }}>
                <div style={{
                  background: "#0a0a0a", border: "1px solid #1c1c1c", borderRadius: 14,
                  padding: "20px 22px", transition: "border-color 0.15s, background 0.15s", cursor: "pointer",
                }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "rgba(255,255,255,0.2)";
                    (e.currentTarget as HTMLElement).style.background = "#111";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.borderColor = "#1c1c1c";
                    (e.currentTarget as HTMLElement).style.background = "#0a0a0a";
                  }}
                >
                  <p style={{ margin: "0 0 8px", fontSize: 18, color: "#fff" }}>{icon}</p>
                  <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "#f5f5f5" }}>{title}</p>
                  <p style={{ margin: 0, fontSize: 12, color: "#505050", lineHeight: 1.5 }}>{desc}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Onboarding nudge */}
        {!user?.onboarding_complete && (
          <div style={{
            background: "#0a0a0a", border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: 14, padding: "20px 24px",
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
          }}>
            <div>
              <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "#f5f5f5" }}>
                Introduce yourself to Vello
              </p>
              <p style={{ margin: 0, fontSize: 13, color: "#505050", lineHeight: 1.5 }}>
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
