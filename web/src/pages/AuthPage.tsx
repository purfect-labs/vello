import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../App";
import { colors, typography, radius } from "../design-system";

type Mode = "login" | "register";

const INPUT: React.CSSProperties = {
  width: "100%", background: colors.surface, border: `1px solid ${colors.border}`,
  borderRadius: radius.md, padding: "11px 14px", fontSize: typography.size.md, color: colors.primary,
  outline: "none", transition: "border-color 0.15s",
};

export default function AuthPage({ mode: initial = "login" }: { mode?: Mode }) {
  const [mode, setMode]         = useState<Mode>(initial);
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const { refreshUser }         = useAuth();
  const navigate                = useNavigate();

  const ERROR_MAP: Record<string, string> = {
    email_taken:         "That email is already registered.",
    invalid_credentials: "Incorrect email or password.",
    password_too_short:  "Password must be at least 8 characters.",
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await api.auth.login(email, password);
      } else {
        await api.auth.register(email, password);
      }
      await refreshUser();
      navigate("/dashboard");
    } catch (err: unknown) {
      const detail = (err as { detail?: string }).detail ?? "request_failed";
      setError(ERROR_MAP[detail] ?? "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", background: colors.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 360 }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <p style={{ color: colors.white, fontWeight: typography.weight.extrabold, letterSpacing: "0.3em", fontSize: typography.size.lg, margin: 0 }}>VELLO</p>
          <p style={{ color: colors.borderStrong, fontSize: typography.size.base, marginTop: 8 }}>Your personal life agent</p>
        </div>

        <div style={{ background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: radius.xl, padding: 32 }}>
          <div style={{ display: "flex", borderBottom: `1px solid ${colors.border}`, marginBottom: 28 }}>
            {(["login", "register"] as Mode[]).map((m) => (
              <button key={m} onClick={() => { setMode(m); setError(""); }}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  padding: "0 4px 14px", marginRight: 20,
                  fontSize: typography.size.md, fontWeight: typography.weight.semibold,
                  color: mode === m ? colors.white : colors.borderStrong,
                  borderBottom: mode === m ? `2px solid ${colors.white}` : "2px solid transparent",
                  transition: "all 0.15s",
                }}>
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: typography.size.sm, color: colors.muted }}>Email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                required autoFocus placeholder="you@example.com" style={INPUT}
                onFocus={(e) => (e.currentTarget.style.borderColor = colors.white)}
                onBlur={(e)  => (e.currentTarget.style.borderColor = colors.border)} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontSize: typography.size.sm, color: colors.muted }}>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                required placeholder={mode === "register" ? "Minimum 8 characters" : ""} style={INPUT}
                onFocus={(e) => (e.currentTarget.style.borderColor = colors.white)}
                onBlur={(e)  => (e.currentTarget.style.borderColor = colors.border)} />
            </div>

            {error && <p style={{ color: colors.error, fontSize: typography.size.sm, margin: 0 }}>{error}</p>}

            <button type="submit" disabled={loading} className="btn-primary"
              style={{ width: "100%", marginTop: 4, fontSize: typography.size.md, padding: 13 }}>
              {loading ? "…" : mode === "login" ? "Sign in" : "Create account →"}
            </button>
          </form>

          {mode === "register" && (
            <p style={{ fontSize: typography.size.sm, color: colors.borderStrong, textAlign: "center", marginTop: 20, lineHeight: typography.lineHeight.normal }}>
              No credit card required. Your data stays yours.
            </p>
          )}
        </div>

        <div style={{ textAlign: "center", marginTop: 24 }}>
          <Link to="/" style={{ fontSize: typography.size.sm, color: colors.faint, textDecoration: "none" }}>← Back</Link>
        </div>
      </div>
    </div>
  );
}
