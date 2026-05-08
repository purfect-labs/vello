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

  gaps: {
    list: () => request<Array<{ type: string; domain: string; description: string; pattern_key?: string }>>("/gaps/"),
    context: () => request<{ context: string }>("/gaps/context"),
  },

  briefing: {
    getPreferences: () => request<{ enabled: boolean; hour: number }>("/briefing/preferences"),
    updatePreferences: (body: { enabled?: boolean; hour?: number }) =>
      request("/briefing/preferences", { method: "PATCH", body: JSON.stringify(body) }),
    sendTest: () => request("/briefing/send-test", { method: "POST" }),
  },

  webhook: {
    getToken: () => request<{ token: string | null }>("/webhook/token"),
    regenerateToken: () => request<{ token: string }>("/webhook/token/regenerate", { method: "POST" }),
  },

  household: {
    get: () => request<{ id: string; owner_user_id: string; name: string | null; address: string | null; timezone: string }>("/household/"),
    update: (body: { name?: string; address?: string; timezone?: string }) =>
      request("/household/", { method: "PATCH", body: JSON.stringify(body) }),
    listMembers: () => request<Array<{ id: string; kind: string; name: string; relationship: string | null; channels: Record<string, string>; consent: Record<string, boolean> }>>("/household/members"),
    addMember: (body: { kind: string; name: string; relationship?: string; channels?: Record<string, string>; consent?: Record<string, boolean> }) =>
      request<{ id: string }>("/household/members", { method: "POST", body: JSON.stringify(body) }),
    removeMember: (id: string) => request(`/household/members/${id}`, { method: "DELETE" }),
    listVendors: (kind?: string) =>
      request<Array<{ id: string; name: string; kind: string; phone: string | null; email: string | null }>>(`/household/vendors${kind ? `?kind=${kind}` : ""}`),
    addVendor: (body: { name: string; kind?: string; phone?: string; email?: string }) =>
      request<{ id: string }>("/household/vendors", { method: "POST", body: JSON.stringify(body) }),
    removeVendor: (id: string) => request(`/household/vendors/${id}`, { method: "DELETE" }),
  },

  lists: {
    getAll: () => request<Array<{ id: string; slug: string; label: string; kind: string; items: Array<{ id: string; label: string; qty: string | null; status: string }> }>>("/lists/"),
    create: (body: { slug: string; label?: string; kind?: string }) =>
      request<{ id: string; slug: string }>("/lists/", { method: "POST", body: JSON.stringify(body) }),
    addItem: (listId: string, body: { label: string; qty?: string }) =>
      request<{ id: string }>(`/lists/${listId}/items`, { method: "POST", body: JSON.stringify(body) }),
    updateItem: (listId: string, itemId: string, status: string) =>
      request(`/lists/${listId}/items/${itemId}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    deleteItem: (listId: string, itemId: string) =>
      request(`/lists/${listId}/items/${itemId}`, { method: "DELETE" }),
  },

  inventory: {
    list: (lowStock?: boolean) =>
      request<Array<{ id: string; label: string; last_used_at: string | null; est_lifetime_days: number | null; low_threshold_days: number | null }>>(`/inventory/${lowStock ? "?low_stock=true" : ""}`),
    add: (body: { label: string; est_lifetime_days?: number; low_threshold_days?: number; restock_url?: string }) =>
      request<{ id: string }>("/inventory/", { method: "POST", body: JSON.stringify(body) }),
    action: (id: string, action: "restocked" | "used" | "lost") =>
      request(`/inventory/${id}/action`, { method: "POST", body: JSON.stringify({ action }) }),
    delete: (id: string) => request(`/inventory/${id}`, { method: "DELETE" }),
  },

  drafts: {
    list: (status?: string) =>
      request<Array<{ id: string; tool_name: string; summary: string; status: string; tool_args_json: string; created_at: string }>>(`/drafts/${status ? `?status=${status}` : ""}`),
    confirm: (id: string) => request<{ ok: boolean; result: unknown }>(`/drafts/${id}/confirm`, { method: "POST" }),
    dismiss: (id: string) => request(`/drafts/${id}/dismiss`, { method: "POST" }),
    edit: (id: string, args: Record<string, unknown>) =>
      request(`/drafts/${id}/edit`, { method: "PATCH", body: JSON.stringify({ args }) }),
  },

  agent: {
    trigger: (kind: string, payload?: Record<string, unknown>) =>
      request<{ session_id: string; outcome: string; steps: number; drafts_created: unknown[]; need_info: string | null; finish_message: string | null; quality: unknown }>("/agent/trigger", { method: "POST", body: JSON.stringify({ kind, payload }) }),
    sessions: (limit?: number) =>
      request<Array<{ id: string; trigger_kind: string; outcome: string; steps: number; started_at: string; ended_at: string | null }>>(`/agent/sessions${limit ? `?limit=${limit}` : ""}`),
    getSession: (id: string) => request(`/agent/sessions/${id}`),
    campaigns: () =>
      request<Array<{ id: string; intent: string; summary: string | null; status: string; expires_at: string | null; created_at: string }>>("/agent/campaigns"),
    createCampaign: (body: { intent: string; summary?: string; watcher?: Record<string, unknown>; expires_in_days?: number }) =>
      request<{ id: string }>("/agent/campaigns", { method: "POST", body: JSON.stringify(body) }),
    closeCampaign: (id: string) => request(`/agent/campaigns/${id}/close`, { method: "POST" }),
    getPolicy: () => request<Record<string, unknown>>("/agent/policy"),
    setPolicy: (policy: Record<string, unknown>) =>
      request("/agent/policy", { method: "PUT", body: JSON.stringify(policy) }),
    promotionCandidates: () =>
      request<Array<{ tool: string; confirmed: number; dismissed: number }>>("/agent/promotion-candidates"),
    acceptPromotion: (tool: string) =>
      request<{ ok: boolean; tool: string; approval: string }>(`/agent/promotion-candidates/${tool}/accept`, { method: "POST" }),
    getCost: () =>
      request<{ day: string; total_usd: number; cap_usd: number; remaining_usd: number; cap_reached: boolean; by_integration: Array<{ integration: string; cost_usd: number; calls: number }> }>("/agent/cost"),
    setCostCap: (cap_usd: number) =>
      request("/agent/cost/cap", { method: "PUT", body: JSON.stringify({ cap_usd }) }),
  },

  playbooks: {
    list: () => request<Array<{ id: string; slug: string; title: string; source: string; enabled: number; usage_count: number }>>("/playbooks/"),
    run: (id: string) => request<{ session_id: string; outcome: string; drafts_created: unknown[] }>(`/playbooks/${id}/run`, { method: "POST" }),
    acceptLearned: (id: string) => request(`/playbooks/${id}/accept-learned`, { method: "POST" }),
    disable: (id: string) => request(`/playbooks/${id}`, { method: "DELETE" }),
  },
};
