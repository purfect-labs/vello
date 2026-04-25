import { useState } from "react";
import Nav from "../components/Nav";
import { api } from "../api";
import { useAuth } from "../App";

const INPUT: React.CSSProperties = {
  background: "#0a0a0a", border: "1px solid #1c1c1c", borderRadius: 10,
  padding: "11px 14px", fontSize: 14, color: "#f5f5f5", outline: "none",
  width: "100%", transition: "border-color 0.15s", fontFamily: "inherit",
};

function SettingCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div style={{ background: "#0a0a0a", border: "1px solid #1c1c1c", borderRadius: 14, padding: "24px 24px", marginBottom: 16 }}>
      <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 600, color: "#f5f5f5" }}>{title}</p>
      <p style={{ margin: "0 0 20px", fontSize: 13, color: "#505050", lineHeight: 1.5 }}>{description}</p>
      {children}
    </div>
  );
}

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();

  const [kortexToken, setKortexToken]   = useState("");
  const [connecting, setConnecting]     = useState(false);
  const [connectError, setConnectError] = useState("");
  const [connectOk, setConnectOk]       = useState(false);

  const [importing, setImporting]     = useState(false);
  const [importResult, setImportResult] = useState<{ imported: number; email: string } | null>(null);

  const [disconnecting, setDisconnecting] = useState(false);

  async function connectKortex() {
    if (!kortexToken.trim()) return;
    setConnecting(true); setConnectError(""); setConnectOk(false);
    try {
      await api.kortex.connect(kortexToken.trim());
      setConnectOk(true);
      setKortexToken("");
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
    setDisconnecting(false);
    setConnectOk(false);
    setImportResult(null);
  }

  return (
    <div style={{ minHeight: "100vh", background: "#000", display: "flex", flexDirection: "column" }}>
      <Nav />

      <div style={{ maxWidth: 640, margin: "0 auto", width: "100%", padding: "48px 24px" }}>
        <div style={{ marginBottom: 40 }}>
          <p style={{ margin: "0 0 6px", fontSize: 11, color: "#505050", fontWeight: 700, letterSpacing: "0.12em" }}>SETTINGS</p>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-0.03em" }}>Configure Vello</h1>
        </div>

        {/* Kortex connection */}
        <SettingCard
          title="Connect Kortex"
          description="Link your Kortex account so Vello can pull your existing profile — goals, health context, work patterns — and skip the cold start."
        >
          {user?.has_kortex ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#22c55e", display: "inline-block" }} />
                <span style={{ fontSize: 13, color: "#f5f5f5" }}>Kortex connected</span>
              </div>

              {importResult && (
                <p style={{ fontSize: 13, color: "#888", margin: 0 }}>
                  ✓ Imported {importResult.imported} context entries from {importResult.email}
                </p>
              )}

              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={importFromKortex} disabled={importing} className="btn-primary" style={{ fontSize: 13 }}>
                  {importing ? "Importing…" : "Sync from Kortex"}
                </button>
                <button onClick={disconnectKortex} disabled={disconnecting} className="btn-ghost" style={{ fontSize: 13 }}>
                  {disconnecting ? "…" : "Disconnect"}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: "#505050", display: "block", marginBottom: 6 }}>
                  Kortex API token
                </label>
                <p style={{ fontSize: 11, color: "#333", margin: "0 0 8px", lineHeight: 1.5 }}>
                  Find yours in Kortex → Profile → API Token. Starts with <code style={{ color: "#555" }}>ktx_</code>
                </p>
                <input
                  type="password"
                  value={kortexToken}
                  onChange={(e) => setKortexToken(e.target.value)}
                  placeholder="ktx_…"
                  style={INPUT}
                  onFocus={(e) => (e.currentTarget.style.borderColor = "#333")}
                  onBlur={(e) => (e.currentTarget.style.borderColor = "#1c1c1c")}
                />
              </div>

              {connectError && <p style={{ fontSize: 12, color: "#ef4444", margin: 0 }}>{connectError}</p>}
              {connectOk    && <p style={{ fontSize: 12, color: "#22c55e", margin: 0 }}>Connected successfully.</p>}

              <button onClick={connectKortex} disabled={connecting || !kortexToken.trim()} className="btn-primary" style={{ fontSize: 13, alignSelf: "flex-start" }}>
                {connecting ? "Connecting…" : "Connect Kortex →"}
              </button>
            </div>
          )}
        </SettingCard>

        {/* Account */}
        <SettingCard
          title="Account"
          description="Your Vello account details."
        >
          <p style={{ margin: 0, fontSize: 14, color: "#f5f5f5" }}>{user?.email}</p>
        </SettingCard>

        {/* Android app */}
        <SettingCard
          title="Android App"
          description="The Android app enables geolocation, push notifications, SMS coordination, and background routine learning — the features that make Vello truly proactive."
        >
          <div style={{
            display: "flex", alignItems: "center", gap: 8, padding: "10px 16px",
            border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, alignSelf: "flex-start", width: "fit-content",
          }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#fff", display: "inline-block" }} className="animate-pulse" />
            <span style={{ fontSize: 12, color: "#888", fontWeight: 600 }}>Android app — coming soon</span>
          </div>
        </SettingCard>
      </div>
    </div>
  );
}
