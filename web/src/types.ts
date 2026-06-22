export type Vec3 = [number, number, number];

export interface Telemetry {
  current_task?: string;
  current_file?: string;
  progress?: number;
  tokens_in?: number;
  tokens_out?: number;
  model?: string;
  context_window?: { used: number; max: number };
}

export interface AgentMarker {
  id: string;
  name: string;
  color: string;
  state: string;
  home: string;
  position: Vec3;
  target: Vec3;
  telemetry: Telemetry;
  // A hand-off errand: this agent carries the task to the next agent and returns.
  errand?: { to: [number, number]; mode: string; t0: number };
}

export interface Primitive {
  id: string;
  type: string;
  name: string;
  transform: { position: Vec3; rotation: Vec3; scale: Vec3 };
  appearance: { material: string; opacity: number; edgeGlow: boolean; color: string };
  tags: string[];
  bindings: { channel: string; to: string }[];
  interactions: string[];
  active: boolean;
}

export interface Scene {
  space_id: string;
  room: { width: number; depth: number; height: number; grid: number };
  primitives: Primitive[];
  agents: AgentMarker[];
}

export interface SamsEvent {
  id: string;
  type: string;
  ts: string;
  actor?: string | null;
  space?: string | null;
  payload: Record<string, any>;
  trace_id?: string | null;
}

export interface Card {
  id: string;
  title: string;
  status: string;
  assignee: string | null;
  labels: string[];
  priority: string;
  milestone: string | null;
  progress: number;
  checklist: { item: string; done: boolean }[];
  github_item: number | null;
  description: string;
  project: string | null;
  stage_status: string;
  outputs: Record<string, string>;
  gate_id: string | null;
  image?: string | null;
}

export interface ProjectProc {
  pid: number;
  name: string;
  path: string;
  command: string;
  kind: string;
  log: string;
  alive: boolean;
}

export interface Status {
  version: string;
  mode: string;
  environment: string;
  agents_online: number;
  spaces: string[];
  posture: { mode: string; gates: string; permissions: string; confirmations: string };
  events: number;
  pending_gates: number;
}
