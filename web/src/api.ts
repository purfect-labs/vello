const BASE = "/api/v1";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...((init.headers as Record<string, string>) || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err: Error & { detail?: string } = new Error(body.detail || "request_failed");
    (err as unknown as { detail: string }).detail = body.detail || "request_failed";
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  auth: {
    register: (email: string, password: string) =>
      request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
    login: (email: string, password: string) =>
      request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
    logout: () => request("/auth/logout", { method: "POST" }),
    me: () => request<{ id: string; email: string; onboarding_complete: boolean; has_kortex: boolean }>("/auth/me"),
  },

  dialogue: {
    history: () => request<Array<{ role: string; content: string; created_at: string }>>("/dialogue/history"),
    send: (message: string) =>
      request<{ message: string; extracted: unknown[]; suggest_next: string | null; onboarding_complete: boolean }>(
        "/dialogue/", { method: "POST", body: JSON.stringify({ message }) }
      ),
    start: () => request<{ message: string | null; already_started: boolean }>("/dialogue/start", { method: "POST" }),
  },

  context: {
    getAll: () => request<Record<string, { label: string; description: string; keys: string[]; data: Record<string, { value: string; source: string }> }>>("/context/"),
    upsert: (domain: string, key: string, value: string) =>
      request("/context/", { method: "PUT", body: JSON.stringify({ domain, key, value }) }),
    delete: (domain: string, key: string) =>
      request(`/context/${domain}/${key}`, { method: "DELETE" }),
  },

  contacts: {
    list: () => request<Array<{ id: string; label: string; name: string; phone: string | null; notify_mode: string }>>("/contacts/"),
    create: (body: { label: string; name: string; phone?: string; notify_mode?: string }) =>
      request<{ id: string }>("/contacts/", { method: "POST", body: JSON.stringify(body) }),
    delete: (id: string) => request(`/contacts/${id}`, { method: "DELETE" }),
  },

  routines: {
    list: () => request<Array<{ id: string; name: string; type: string; schedule: Record<string, unknown>; active: boolean }>>("/routines/"),
    create: (body: { name: string; type: string; schedule?: Record<string, unknown> }) =>
      request<{ id: string }>("/routines/", { method: "POST", body: JSON.stringify(body) }),
    toggle: (id: string, active: boolean) =>
      request(`/routines/${id}`, { method: "PATCH", body: JSON.stringify({ active }) }),
    delete: (id: string) => request(`/routines/${id}`, { method: "DELETE" }),
  },

  zones: {
    list: () => request<Array<{ id: string; label: string; type: string; address: string | null }>>("/zones/"),
    create: (body: { label: string; type: string; address?: string; radius_meters?: number }) =>
      request<{ id: string }>("/zones/", { method: "POST", body: JSON.stringify(body) }),
    delete: (id: string) => request(`/zones/${id}`, { method: "DELETE" }),
  },

  inferences: {
    list: () => request<Array<{ id: string; description: string; proposed: Record<string, unknown> }>>("/inferences/"),
    confirm: (id: string) => request(`/inferences/${id}/confirm`, { method: "POST" }),
    dismiss: (id: string) => request(`/inferences/${id}/dismiss`, { method: "POST" }),
  },

  kortex: {
    connect: (token: string) =>
      request("/kortex/connect", { method: "POST", body: JSON.stringify({ token }) }),
    import: () => request<{ imported: number; signals_fired: number; email: string }>("/kortex/import", { method: "POST" }),
    disconnect: () => request("/kortex/disconnect", { method: "DELETE" }),
  },

  signals: {
    list: () => request<import("./types").SignalTrigger[]>("/signals/"),
    confirm: (id: string) => request(`/signals/${id}/confirm`, { method: "POST" }),
    dismiss: (id: string) => request(`/signals/${id}/dismiss`, { method: "POST" }),
  },

  temporal: {
    observe: (pattern_key: string, label: string, minutes?: number) =>
      request("/temporal/observe", { method: "POST", body: JSON.stringify({ pattern_key, label, minutes }) }),
    patterns: () => request<import("./types").TemporalPattern[]>("/temporal/patterns"),
    predict: (pattern_key: string) => request<import("./types").TemporalPattern>(`/temporal/predict/${pattern_key}`),
    deviations: () => request<import("./types").TemporalDeviation[]>("/temporal/deviations"),
  },
};
