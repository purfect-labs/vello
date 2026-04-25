export interface User {
  id: string;
  email: string;
  onboarding_complete: boolean;
  has_kortex: boolean;
}

export interface ContextEntry {
  value: string;
  source: "manual" | "conversation" | "inferred" | "kortex";
  confidence: number;
}

export interface ContextDomain {
  label: string;
  description: string;
  keys: string[];
  data: Record<string, ContextEntry>;
}

export interface DialogueTurn {
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface Contact {
  id: string;
  label: string;
  name: string;
  phone: string | null;
  notify_mode: "confirm" | "auto" | "draft";
  created_at: string;
}

export interface Routine {
  id: string;
  name: string;
  type: string;
  schedule: Record<string, unknown>;
  active: boolean;
  confidence: number;
  source: string;
  created_at: string;
}

export interface Zone {
  id: string;
  label: string;
  type: "home" | "work" | "gym" | "custom";
  address: string | null;
  lat: number | null;
  lng: number | null;
  radius_meters: number;
  created_at: string;
}

export interface PendingInference {
  id: string;
  inference_type: string;
  description: string;
  proposed: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface ActionLog {
  id: string;
  action_type: string;
  description: string;
  status: string;
  created_at: string;
}

export interface SignalTrigger {
  id: string;
  signal_id: string;
  label: string;
  priority: "high" | "medium" | "low";
  action_type: string;
  trigger_message: string;
  created_at: string;
  expires_at: string;
}

export interface TemporalPattern {
  pattern_key: string;
  label: string;
  mean_minutes: number | null;
  std_dev_minutes: number | null;
  sample_count: number;
  typical_days: number[];
  last_updated: string;
}

export interface TemporalDeviation {
  pattern_key: string;
  label: string;
  expected_time: string;
  current_time: string;
  late_by_minutes: number;
  message: string;
}
