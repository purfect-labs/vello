import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../App";
import { V } from "../vello-tokens";

type Mode = "login" | "register";

function VelloMark() {
  return (
    <svg width={32} height={32} viewBox="0 0 24 24">
      <g stroke={V.ink} strokeWidth="1.2" fill="none" strokeLinecap="round">
        <circle cx="12" cy="12" r="3.2" />
        {[0, 60, 120, 180, 240, 300].map(a => {
          const rad = (a * Math.PI) / 180;
          return <line key={a}
            x1={12 + Math.cos(rad) * 5.2} y1={12 + Math.sin(rad) * 5.2}
            x2={12 + Math.cos(rad) * 9.8} y2={12 + Math.sin(rad) * 9.8} />;
        })}
      </g>
      <circle cx="12" cy="12" r="1" fill={V.amber} />
    </svg>
  );
}

export default function AuthPage({ mode: initial = "login" }: { mode?: Mode }) {
  const [mode, setMode]         = useState<Mode>(initial);
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [emailFocus, setEmailFocus]   = useState(false);
  const [passFocus, setPassFocus]     = useState(false);
  const { refreshUser }         = useAuth();
  const navigate                = useNavigate();

  const ERROR_MAP: Record<string, string> = {
    email_taken:         "that email is already registered.",
    invalid_credentials: "incorrect email or password.",
    password_too_short:  "password must be at least 8 characters.",
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
      setError(ERROR_MAP[detail] ?? "something went wrong. please try again.");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = (focused: boolean): React.CSSProperties => ({
    width: "100%", background: V.surface,
    border: `1px solid ${focused ? V.borderHi : V.border}`,
    borderRadius: 10, padding: "11px 14px", fontSize: 14,
    color: V.ink, outline: "none", transition: "border-color .2s",
    fontFamily: V.sans,
  });

  return (
    <div style={{
      minHeight: "100vh", background: V.bg,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      padding: 24,
    }}>
      {/* ambient bloom */}
      <div style={{
        position: "fixed", top: "40%", left: "50%",
        width: 600, height: 600, borderRadius: "50%",
        background: `radial-gradient(circle, ${V.amberGlow} 0%, transparent 60%)`,
        filter: "blur(120px)", opacity: 0.2,
        transform: "translate(-50%, -50%)", pointerEvents: "none",
      }} />

      <div style={{ width: "100%", maxWidth: 360, position: "relative" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <VelloMark />
            <span style={{ fontFamily: V.sans, fontWeight: 800, fontSize: 13, letterSpacing: "0.34em", color: V.ink }}>VELLO</span>
          </div>
          <p style={{ margin: 0, fontFamily: V.serif, fontStyle: "italic", fontSize: 15, color: V.inkDim }}>
            your personal life agent
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: V.surface, border: `1px solid ${V.border}`,
          borderRadius: 18, padding: 32,
          boxShadow: "0 40px 80px -30px rgba(245,158,11,0.12), 0 0 0 1px rgba(255,255,255,0.04)",
        }}>
          {/* Mode tabs */}
          <div style={{ display: "flex", borderBottom: `1px solid ${V.hairline}`, marginBottom: 28 }}>
            {(["login", "register"] as Mode[]).map(m => (
              <button key={m} onClick={() => { setMode(m); setError(""); }}
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  padding: "0 4px 14px", marginRight: 20,
                  fontFamily: V.sans, fontSize: 14, fontWeight: 500,
                  color: mode === m ? V.ink : V.inkFaint,
                  borderBottom: mode === m ? `1px solid ${V.amber}` : "1px solid transparent",
                  transition: "color .2s",
                }}>
                {m === "login" ? "sign in" : "create account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontFamily: V.mono, fontSize: 10, color: V.inkFaint, letterSpacing: "0.16em", textTransform: "uppercase" }}>email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                required autoFocus placeholder="you@example.com"
                style={inputStyle(emailFocus)}
                onFocus={() => setEmailFocus(true)}
                onBlur={() => setEmailFocus(false)} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <label style={{ fontFamily: V.mono, fontSize: 10, color: V.inkFaint, letterSpacing: "0.16em", textTransform: "uppercase" }}>password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                required placeholder={mode === "register" ? "minimum 8 characters" : ""}
                style={inputStyle(passFocus)}
                onFocus={() => setPassFocus(true)}
                onBlur={() => setPassFocus(false)} />
            </div>

            {error && (
              <p style={{ margin: 0, fontFamily: V.sans, fontSize: 13, color: V.bad }}>{error}</p>
            )}

            <button type="submit" disabled={loading} style={{
              fontFamily: V.sans, fontSize: 14, fontWeight: 600,
              color: "#100c06", background: loading ? V.inkFaint : V.ink,
              border: "none", borderRadius: 999, padding: "12px",
              cursor: loading ? "default" : "pointer",
              marginTop: 4, width: "100%",
              transition: "background .2s",
              boxShadow: loading ? "none" : "0 4px 20px rgba(245,158,11,0.15)",
            }}>
              {loading ? "…" : mode === "login" ? "sign in" : "create account →"}
            </button>
          </form>

          {mode === "register" && (
            <p style={{ fontFamily: V.sans, fontSize: 12, color: V.inkFaint, textAlign: "center", marginTop: 20, lineHeight: 1.5 }}>
              no credit card required. your data stays yours.
            </p>
          )}
        </div>

        <div style={{ textAlign: "center", marginTop: 24 }}>
          <Link to="/" style={{ fontFamily: V.mono, fontSize: 10, letterSpacing: "0.14em", color: V.inkFaint, textDecoration: "none", textTransform: "uppercase" }}>
            ← back
          </Link>
        </div>
      </div>
    </div>
  );
}
