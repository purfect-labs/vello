import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../App";
import { V } from "../vello-tokens";

const LINKS = [
  { to: "/dashboard", label: "briefing"  },
  { to: "/dialogue",  label: "dialogue"  },
  { to: "/profile",   label: "context"   },
  { to: "/routines",  label: "routines"  },
  { to: "/settings",  label: "settings"  },
];

function VelloMark() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24">
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

function NavLink({ to, label, active }: { to: string; label: string; active: boolean }) {
  const [hover, setHover] = useState(false);
  return (
    <Link to={to}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        fontFamily: V.mono, fontSize: 11, letterSpacing: "0.16em",
        textTransform: "uppercase" as const,
        color: active ? V.ink : hover ? V.inkDim : V.inkFaint,
        textDecoration: "none", transition: "color .2s",
        paddingBottom: 2,
        borderBottom: active ? `1px solid ${V.amber}` : "1px solid transparent",
      }}>{label}</Link>
  );
}

export default function Nav() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [hoverOut, setHoverOut] = useState(false);

  return (
    <nav style={{
      position: "sticky", top: 0, zIndex: 50,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 32px", height: 52,
      background: "rgba(0,0,0,0.8)",
      backdropFilter: "blur(20px) saturate(140%)",
      WebkitBackdropFilter: "blur(20px) saturate(140%)",
      borderBottom: `1px solid ${V.hairline}`,
      flexShrink: 0,
    }}>
      <Link to="/dashboard" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
        <VelloMark />
        <span style={{ fontFamily: V.sans, fontWeight: 800, fontSize: 11, letterSpacing: "0.34em", color: V.ink }}>VELLO</span>
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
        {LINKS.map(({ to, label }) => {
          const active = pathname === to || (to !== "/dashboard" && pathname.startsWith(to));
          return <NavLink key={to} to={to} label={label} active={active} />;
        })}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontFamily: V.mono, fontSize: 10, color: V.inkFaint, letterSpacing: "0.06em" }}>
          {user?.email}
        </span>
        <button
          onClick={logout}
          onMouseEnter={() => setHoverOut(true)}
          onMouseLeave={() => setHoverOut(false)}
          style={{
            fontFamily: V.mono, fontSize: 10, letterSpacing: "0.14em",
            color: hoverOut ? V.inkDim : V.inkFaint,
            background: "none", border: "none", cursor: "pointer",
            transition: "color .2s", textTransform: "uppercase" as const,
          }}>
          sign out
        </button>
      </div>
    </nav>
  );
}
