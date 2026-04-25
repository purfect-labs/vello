import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../App";

const LINKS = [
  { to: "/",         label: "Dashboard" },
  { to: "/dialogue", label: "Dialogue"  },
  { to: "/profile",  label: "Profile"   },
  { to: "/routines", label: "Routines"  },
  { to: "/settings", label: "Settings"  },
];

export default function Nav() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();

  return (
    <nav style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 24px", height: 56,
      borderBottom: "1px solid #1c1c1c",
      background: "#000000",
      flexShrink: 0,
    }}>
      <Link to="/" style={{ color: "#ffffff", fontWeight: 800, letterSpacing: "0.3em", fontSize: 13, textDecoration: "none" }}>
        VELLO
      </Link>

      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        {LINKS.map(({ to, label }) => {
          const active = to === "/" ? pathname === "/" : pathname.startsWith(to);
          return (
            <Link
              key={to}
              to={to}
              style={{
                color: active ? "#f5f5f5" : "#505050",
                fontSize: 13, textDecoration: "none", transition: "color 0.15s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = "#f5f5f5")}
              onMouseLeave={(e) => (e.currentTarget.style.color = active ? "#f5f5f5" : "#505050")}
            >
              {label}
            </Link>
          );
        })}

        <span style={{ color: "#2a2a2a", fontSize: 12 }}>{user?.email}</span>
        <button
          onClick={logout}
          style={{ color: "#404040", fontSize: 12, background: "none", border: "none", cursor: "pointer", transition: "color 0.15s" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#f5f5f5")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#404040")}
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
