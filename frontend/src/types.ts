export type Role = "fan" | "volunteer" | "organizer" | "staff";

export interface RoleInfo {
  role: Role;
  description: string;
  tools: string[];
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface ToolEvent {
  name: string;
  args: Record<string, unknown>;
  result: Record<string, unknown> | string;
  error: boolean;
}

export interface ChatResponse {
  reply: string;
  role: Role;
  language: string;
  tool_events: ToolEvent[];
  snapshot_summary: string;
}

export interface CrowdDensity {
  zone_id: string;
  zone_name: string;
  level: string;
  occupancy: number;
  capacity: number;
  density: number;
  level_label: string;
}

export interface GateStatus {
  gate_id: string;
  label: string;
  status: string;
  throughput_per_min: number;
  queue_minutes: number;
}

export interface Incident {
  incident_id: string;
  type: string;
  location: string;
  severity: string;
  status: string;
  description: string;
}

export interface TransitLoad {
  node_id: string;
  name: string;
  mode: string;
  congestion: string;
  wait_minutes: number;
}

export interface MatchState {
  match_id: string;
  name: string;
  phase: string;
  sim_time: number;
  kickoff_at: number;
  halftime_at: number;
  full_time_at: number;
}

export interface StadiumSnapshot {
  venue_name: string;
  match: MatchState;
  crowd: CrowdDensity[];
  gates: GateStatus[];
  incidents: Incident[];
  transit: TransitLoad[];
}
