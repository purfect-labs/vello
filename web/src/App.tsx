import { createContext, useContext, useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import type { User } from "./types";
import AuthPage from "./pages/AuthPage";
import DashboardPage from "./pages/DashboardPage";
import DialoguePage from "./pages/DialoguePage";
import LifeContextPage from "./pages/LifeContextPage";
import RoutinesPage from "./pages/RoutinesPage";
import SettingsPage from "./pages/SettingsPage";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({
  user: null, loading: true,
  refreshUser: async () => {}, logout: async () => {},
});

export function useAuth() { return useContext(AuthContext); }

function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    try {
      const u = await api.auth.me();
      setUser(u as User);
    } catch {
      setUser(null);
    }
  }

  async function logout() {
    await api.auth.logout().catch(() => {});
    setUser(null);
  }

  useEffect(() => { refreshUser().finally(() => setLoading(false)); }, []);

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div style={{ minHeight: "100vh", background: "#000", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <span style={{ color: "#333", fontSize: 12, letterSpacing: "0.2em" }}>VELLO</span>
    </div>
  );
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login"    element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route path="/" element={<Protected><DashboardPage /></Protected>} />
          <Route path="/dialogue" element={<Protected><DialoguePage /></Protected>} />
          <Route path="/profile"  element={<Protected><LifeContextPage /></Protected>} />
          <Route path="/routines" element={<Protected><RoutinesPage /></Protected>} />
          <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
