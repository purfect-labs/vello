import { useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import { useAuth } from "../App";
import { V } from "../vello-tokens";

function Mono({ children, size = 10, color, style }: {
  children: React.ReactNode; size?: number; color?: string; style?: React.CSSProperties;
}) {
  return <span style={{ fontFamily: V.mono, fontSize: size, color: color || V.inkDim, letterSpacing: "0.04em", ...style }}>{children}</span>;
}

function SettingCard({ title, description, children }: {
  title: string; description: string; children: React.ReactNode;
}) {
  return (
    <div style={{
      background: V.surface, border: `1px solid ${V.border}`,
      borderRadius: 14, padding: "24px 26px", marginBottom: 14,
    }}>
      <p style={{ margin: "0 0 4px", fontFamily: V.serif, fontSize: 17, color: V.ink, fontWeight: 400 }}>{title}</p>
      <p style={{ margin: "0 0 22px", fontFamily: V.sans, fontSize: 13, color: V.inkDim, lineHeight: 1.55 }}>{description}</p>
      {children}
    </div>
  );
}

function PrimaryBtn({ children, onClick, disabled }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick} disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.sans, fontSize: 13, fontWeight: 600,
        color: "#100c06", background: disabled ? V.inkFaint : V.ink,
        border: "none", borderRadius: 999, padding: "9px 20px",
        cursor: disabled ? "default" : "pointer",
        boxShadow: hover && !disabled ? "0 4px 20px rgba(245,158,11,0.2)" : "none",
        transition: "box-shadow .2s, background .2s",
      }}>{children}</button>
  );
}

function GhostBtn({ children, onClick, disabled }: {
  children: React.ReactNode; onClick: () => void; disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);
  return (
    <button onClick={onClick} disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.sans, fontSize: 13, fontWeight: 500,
        color: disabled ? V.inkFaint : V.ink, background: "transparent",
        border: `1px solid ${hover && !disabled ? V.borderHi : V.border}`,
        borderRadius: 999, padding: "8px 18px",
        cursor: disabled ? "default" : "pointer", transition: "border-color .2s",
      }}>{children}</button>
  );
}

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();

  const [kortexToken, setKortexToken]     = useState("");
  const [connecting, setConnecting]       = useState(false);
  const [connectError, setConnectError]   = useState("");
  const [connectOk, setConnectOk]         = useState(false);
  const [importing, setImporting]         = useState(false);
  const [importResult, setImportResult]   = useState<{ imported: number; email: string } | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const [tokenFocus, setTokenFocus]       = useState(false);

  async function connectKortex() {
    if (!kortexToken.trim()) return;
    setConnecting(true); setConnectError(""); setConnectOk(false);
    try {
      await api.kortex.connect(kortexToken.trim());
      setConnectOk(true); setKortexToken("");
      await refreshUser();
    } catch (err: unknown) {
      const detail = (err as { detail?: string }).detail ?? "request_failed";
      setConnectError(
        detail === "kortex_token_invalid" ? "Token not recognized by Kortex." :
        detail === "invalid_token_format" ? "Token must start with ktx_" :
        "Could not connect. Check your token and try again."
      );
    } finally {
      setConnecting(false);
    }
  }

  async function importFromKortex() {
    setImporting(true); setImportResult(null);
    try {
      const r = await api.kortex.import();
      setImportResult(r as { imported: number; email: string });
    } catch {
      setConnectError("Import failed. Check your Kortex connection.");
    } finally {
      setImporting(false);
    }
  }

  async function disconnectKortex() {
    setDisconnecting(true);
    await api.kortex.disconnect().catch(() => {});
    await refreshUser();
    setDisconnecting(false); setConnectOk(false); setImportResult(null);
  }

  return (
    <div style={{ minHeight: "100vh", background: V.bg, display: "flex", flexDirection: "column" }}>
      <Nav />
      <div style={{ maxWidth: 640, margin: "0 auto", width: "100%", padding: "52px 24px" }}>

        <div style={{ marginBottom: 48 }}>
          <span style={{ fontFamily: V.mono, fontSize: 10, letterSpacing: "0.2em", color: V.inkFaint, textTransform: "uppercase" }}>settings</span>
          <h1 style={{ margin: "14px 0 0", fontFamily: V.serif, fontWeight: 400, fontSize: "clamp(32px, 4vw, 44px)", color: V.ink, letterSpacing: "-0.02em", lineHeight: 1 }}>
            configure vello.
          </h1>
        </div>

        {/* Kortex connection */}
        <SettingCard
          title="connect kortex"
          description="link your kortex account so vello can pull your existing profile — goals, health context, work patterns — and skip the cold start."
        >
          {user?.has_kortex ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: V.good, boxShadow: `0 0 8px ${V.good}`, display: "inline-block" }} />
                <span style={{ fontFamily: V.sans, fontSize: 14, color: V.ink }}>kortex connected</span>
              </div>
              {importResult && (
                <Mono size={12} color={V.inkDim}>
                  ✓ imported {importResult.imported} context entries from {importResult.email}
                </Mono>
              )}
              <div style={{ display: "flex", gap: 8 }}>
                <PrimaryBtn onClick={importFromKortex} disabled={importing}>
                  {importing ? "importing…" : "sync from kortex"}
                </PrimaryBtn>
                <GhostBtn onClick={disconnectKortex} disabled={disconnecting}>
                  {disconnecting ? "…" : "disconnect"}
                </GhostBtn>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <Mono size={10} color={V.inkFaint} style={{ display: "block", marginBottom: 6, letterSpacing: "0.16em", textTransform: "uppercase" }}>
                  kortex api token
                </Mono>
                <Mono size={10} color={V.inkFaint} style={{ display: "block", marginBottom: 10, lineHeight: 1.6 }}>
                  find yours in kortex → profile → api token. starts with <code style={{ color: V.inkDim }}>ktx_</code>
                </Mono>
                <input
                  type="password"
                  value={kortexToken}
                  onChange={e => setKortexToken(e.target.value)}
                  onFocus={() => setTokenFocus(true)}
                  onBlur={() => setTokenFocus(false)}
                  placeholder="ktx_…"
                  style={{
                    background: V.surfaceHi,
                    border: `1px solid ${tokenFocus ? V.borderHi : V.border}`,
                    borderRadius: 10, padding: "10px 14px", fontSize: 13,
                    color: V.ink, outline: "none", width: "100%",
                    fontFamily: V.mono, transition: "border-color .2s",
                  }}
                />
              </div>
              {connectError && <Mono size={12} color={V.bad}>{connectError}</Mono>}
              {connectOk    && <Mono size={12} color={V.good}>connected successfully.</Mono>}
              <div>
                <PrimaryBtn onClick={connectKortex} disabled={connecting || !kortexToken.trim()}>
                  {connecting ? "connecting…" : "connect kortex →"}
                </PrimaryBtn>
              </div>
            </div>
          )}
        </SettingCard>

        {/* Account */}
        <SettingCard title="account" description="your vello account details.">
          <span style={{ fontFamily: V.mono, fontSize: 13, color: V.ink }}>{user?.email}</span>
        </SettingCard>

        {/* Android app */}
        <SettingCard
          title="android app"
          description="the android app enables geolocation, push notifications, sms coordination, and background routine learning — the features that make vello truly proactive."
        >
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "8px 14px", border: `1px solid ${V.border}`, borderRadius: 999,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: V.inkFaint, display: "inline-block" }} />
            <Mono size={11} color={V.inkFaint} style={{ letterSpacing: "0.12em", textTransform: "uppercase" }}>android app — coming soon</Mono>
          </div>
        </SettingCard>
      </div>
    </div>
  );
}
