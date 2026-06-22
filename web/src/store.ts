import { create } from "zustand";
import type { AgentMarker, Card, ProjectProc, SamsEvent, Scene, Status } from "./types";
import { ROLE_STATIONS, ensureStations } from "./lib/office";
import type { DecorItem } from "./lib/office";

// The office layout (desk positions + decorations) is a user preference, kept in
// localStorage so a rearranged room survives refreshes.
const OFFICE_KEY = "sams.office.v1";
type Stations = Record<string, [number, number]>;
type RoomSize = { width: number; depth: number } | null;

function clampN(v: number, lo: number, hi: number): number { return Math.max(lo, Math.min(hi, v)); }
export const ROOM_MIN = { width: 10, depth: 9 };
export const ROOM_MAX = { width: 32, depth: 28 };

// Keep an item inside the walls — the same bounds the drag uses, so nothing is
// ever stranded outside the floor when the room is resized.
function clampInside(x: number, z: number, W: number, D: number): [number, number] {
  return [clampN(x, 0.7, W - 0.7), clampN(z, 0.7, D - 0.7)];
}
function sanitizeRoom(r: any): RoomSize {
  if (!r || typeof r.width !== "number" || typeof r.depth !== "number" || !isFinite(r.width) || !isFinite(r.depth)) return null;
  return { width: clampN(r.width, ROOM_MIN.width, ROOM_MAX.width), depth: clampN(r.depth, ROOM_MIN.depth, ROOM_MAX.depth) };
}
// Pull every desk + decoration inside W×D, and keep agents heading to their desks.
function fitToRoom(stations: Stations, decor: DecorItem[], agents: Record<string, AgentMarker>, W: number, D: number) {
  const st: Stations = {};
  for (const [id, p] of Object.entries(stations)) st[id] = clampInside(p[0], p[1], W, D);
  const dec = decor.map((d) => ({ ...d, pos: clampInside(d.pos[0], d.pos[1], W, D) }));
  const ag = { ...agents };
  for (const id of Object.keys(ag)) {
    const s = st[id];
    if (s) ag[id] = { ...ag[id], target: [s[0], 0, s[1]] };
  }
  return { stations: st, decor: dec, agents: ag };
}

function loadOffice(): { stations: Stations; decor: DecorItem[]; room: RoomSize } {
  try {
    const raw = localStorage.getItem(OFFICE_KEY);
    const saved = raw ? JSON.parse(raw) : {};
    return { stations: { ...ROLE_STATIONS, ...(saved.stations || {}) }, decor: saved.decor || [], room: sanitizeRoom(saved.room) };
  } catch { return { stations: { ...ROLE_STATIONS }, decor: [], room: null }; }
}
function saveOffice(stations: Stations, decor: DecorItem[], room: RoomSize) {
  try { localStorage.setItem(OFFICE_KEY, JSON.stringify({ stations, decor, room })); } catch { /* ignore */ }
}
const _office = loadOffice();
function randomId(p: string): string { return p + "-" + Math.random().toString(36).slice(2, 8); }

interface LogLine {
  ts: string;
  level: string;
  actor?: string | null;
  message: string;
}

// Where an agent stands per state. `null` = stay at its home station. Idle agents
// rest at home (not all piled in the Lounge) so the office reads as populated.
const STATE_STATION: Record<string, string | null> = {
  reviewing: "Security Gate",
  blocked: "Security Gate",
  paused: "Lounge",
};

// A pipeline column -> the role-agent that works it, and that role's color.
const STAGE_ROLE: Record<string, string> = {
  Planner: "planner", Designer: "designer", Developer: "developer",
  Reviewer: "reviewer", Tester: "tester", Deployer: "deployer",
};
const STAGE_COLOR: Record<string, string> = {
  Planner: "#0EA5E9", Designer: "#F43F5E", Developer: "#3B82F6",
  Reviewer: "#EF4444", Tester: "#2DD4BF", Deployer: "#64748B", "To Do": "#94A3B8",
};

// A "task packet" moving from one agent (or the board) to the next as a card
// advances — the visible hand-off. `mode` varies the choreography.
export type FlightMode = "throw" | "teleport" | "walk" | "lob" | "bounce";
export interface Flight {
  id: string;
  from: [number, number, number];
  to: [number, number, number];
  color: string;
  t0: number;
  mode: FlightMode;
}

// How the finishing agent carries the task to the next agent (≥5 variety).
export type HandoffMode = "walk" | "dash" | "hop" | "teleport" | "spin" | "glide";
const HANDOFF_MODES: HandoffMode[] = ["walk", "walk", "dash", "hop", "teleport", "spin", "glide"];
function pickHandoff(): HandoffMode {
  return HANDOFF_MODES[Math.floor(Math.random() * HANDOFF_MODES.length)];
}

// Deterministic per-agent offset so agents sharing a station fan out in a ring
// instead of stacking on one point.
function offsetFor(id: string): [number, number] {
  let h = 2166136261;
  for (let i = 0; i < id.length; i++) h = (h ^ id.charCodeAt(i)) * 16777619;
  h = h >>> 0;
  const ang = (h % 360) * (Math.PI / 180);
  const rad = 0.7 + ((h >> 9) % 100) / 100 * 1.0; // 0.7..1.7
  return [Math.cos(ang) * rad, Math.sin(ang) * rad];
}

interface SamsState {
  connected: boolean;
  space: string;
  scene: Scene | null;
  agents: Record<string, AgentMarker>;
  tasks: Card[];
  events: SamsEvent[];
  logs: LogLine[];
  status: Status | null;
  selected: { kind: "agent" | "primitive"; id: string } | null;
  openFile: { path: string; content: string } | null;
  selectedRepo: { full_name: string; name: string; default_branch: string } | null;
  selectedPull: { repo: string; number: number; title: string } | null;
  pullsVersion: number;
  runningProjects: ProjectProc[];
  activeProjectPid: number | null;
  flights: Flight[];
  stations: Stations;
  decor: DecorItem[];
  editLayout: boolean;
  roomSize: RoomSize;

  setConnected: (v: boolean) => void;
  applySnapshot: (data: any) => void;
  applyEvent: (e: SamsEvent) => void;
  select: (kind: "agent" | "primitive", id: string) => void;
  setTasks: (t: Card[]) => void;
  setOpenFile: (f: { path: string; content: string } | null) => void;
  openRepo: (repo: { full_name: string; name: string; default_branch: string }) => void;
  closeRepo: () => void;
  openPull: (pull: { repo: string; number: number; title: string }) => void;
  closePull: () => void;
  bumpPulls: () => void;
  setRunningProjects: (p: ProjectProc[]) => void;
  setActiveProject: (pid: number | null) => void;
  removeFlight: (id: string) => void;
  toggleEditLayout: () => void;
  setStation: (id: string, pos: [number, number]) => void;
  addDecor: (type: string) => void;
  moveDecor: (id: string, pos: [number, number]) => void;
  removeDecor: (id: string) => void;
  setRoomSize: (width: number, depth: number) => void;
  resetRoomSize: () => void;
  setAgentColor: (id: string, color: string) => void;
}

export const useStore = create<SamsState>((set, get) => ({
  connected: false,
  space: "main.space",
  scene: null,
  agents: {},
  tasks: [],
  events: [],
  logs: [],
  status: null,
  selected: null,
  openFile: null,
  selectedRepo: null,
  selectedPull: null,
  pullsVersion: 0,
  runningProjects: [],
  activeProjectPid: null,
  flights: [],
  stations: _office.stations,
  decor: _office.decor,
  editLayout: false,
  roomSize: _office.room,

  setConnected: (v) => set({ connected: v }),
  setOpenFile: (f) => set({ openFile: f }),
  openRepo: (repo) => set({ selectedRepo: repo, selectedPull: null }),
  closeRepo: () => set({ selectedRepo: null }),
  openPull: (pull) => set({ selectedPull: pull }),
  closePull: () => set({ selectedPull: null }),
  bumpPulls: () => set((s) => ({ pullsVersion: s.pullsVersion + 1 })),
  setRunningProjects: (p) => set({ runningProjects: p }),
  setActiveProject: (pid) => set({ activeProjectPid: pid }),
  removeFlight: (id) => set((s) => ({ flights: s.flights.filter((f) => f.id !== id) })),

  applySnapshot: (data) => {
    const agents: Record<string, AgentMarker> = {};
    const scene: Scene | null = data.scene ?? null;
    const list = (data.scene?.agents?.length ? data.scene.agents : data.agents) ?? [];
    // Every agent (roles + any spawned instances) gets a dedicated desk slot.
    const ids: string[] = list.map((a: any) => a.agent_id ?? a.id);
    const stations = ensureStations(get().stations, ids);
    for (const a of list) {
      const id = a.agent_id ?? a.id;
      const home = a.home?.primitive ?? a.home ?? "Lounge";
      const state = a.state ?? "idle";
      const pos = homeStation(scene, id, home, stations);
      agents[id] = {
        id, name: a.name, color: a.color, state, home,
        position: pos, target: targetFor(scene, home, state, id, stations),
        telemetry: a.telemetry ?? {},
      };
    }
    saveOffice(stations, get().decor, get().roomSize);
    set({ scene, agents, tasks: data.tasks ?? [], status: data.status, stations });
  },

  applyEvent: (e) => {
    const state = get();
    const events = [...state.events, e].slice(-500);
    const logs = [...state.logs];

    // Build a human log line for the console.
    const line = toLogLine(e);
    if (line) logs.push(line);

    const agents = { ...state.agents };
    const scene = state.scene ? { ...state.scene } : null;
    let stations = state.stations;

    if (e.type === "agent.spawned" && e.actor) {
      const home = e.payload.home ?? "Lounge";
      const st = e.payload.state ?? "initializing";
      // Spawning an agent immediately generates a desk for it.
      stations = ensureStations(stations, [e.actor]);
      saveOffice(stations, state.decor, state.roomSize);
      agents[e.actor] = {
        id: e.actor,
        name: e.payload.name ?? e.actor,
        color: e.payload.color ?? "#9CA3AF",
        state: st,
        home,
        position: homeStation(scene, e.actor, home, stations),
        target: targetFor(scene, home, st, e.actor, stations),
        telemetry: {},
      };
    } else if (e.type === "agent.despawned" && e.actor) {
      delete agents[e.actor];
    } else if (e.type === "agent.state.changed" && e.actor && agents[e.actor]) {
      const m = { ...agents[e.actor] };
      m.state = e.payload.state ?? m.state;
      m.telemetry = { ...m.telemetry, ...(e.payload.telemetry ?? {}) };
      m.target = targetFor(scene, m.home, m.state, e.actor, stations);
      agents[e.actor] = m;
    } else if (e.type === "agent.progress" && e.actor && agents[e.actor]) {
      const m = { ...agents[e.actor] };
      m.telemetry = { ...m.telemetry, progress: e.payload.progress };
      agents[e.actor] = m;
    }

    // Primitive activity glows.
    if (scene && e.type === "vault.file.changed") setPrimitiveActive(scene, "Vault", true);
    if (scene && e.type.startsWith("security.gate."))
      setPrimitiveActive(scene, "Security Gate", e.type === "security.gate.requested");

    // Hand-off: the finishing agent carries the task over to the next agent and
    // returns — the work happens at each agent's OWN station (no flying letter).
    if (e.type === "kanban.card.moved") {
      const A = STAGE_ROLE[e.payload.from];
      const B = STAGE_ROLE[e.payload.to];
      if (A && B && A !== B && agents[A] && agents[B]) {
        const bSt = stations[B];
        const bp: [number, number] = bSt ? [bSt[0], bSt[1]] : [agents[B].position[0], agents[B].position[2]];
        agents[A] = { ...agents[A], errand: { to: bp, mode: pickHandoff(), t0: performance.now() } };
      }
    }

    set({ events, logs: logs.slice(-400), agents, scene, stations });
  },

  select: (kind, id) => set({ selected: { kind, id } }),
  setTasks: (t) => set({ tasks: t }),

  toggleEditLayout: () => set((s) => ({ editLayout: !s.editLayout })),
  setStation: (id, pos) => set((s) => {
    const stations = { ...s.stations, [id]: pos };
    const agents = { ...s.agents };
    // The agent follows its desk (and any pending hand-off errand is dropped).
    if (agents[id]) agents[id] = { ...agents[id], target: [pos[0], 0, pos[1]], errand: undefined };
    saveOffice(stations, s.decor, s.roomSize);
    return { stations, agents };
  }),
  addDecor: (type) => set((s) => {
    const cx = (s.roomSize?.width ?? s.scene?.room.width ?? 12) / 2;
    const cz = (s.roomSize?.depth ?? s.scene?.room.depth ?? 10) / 2;
    const decor = [...s.decor, { id: randomId("decor"), type, pos: [cx, cz] as [number, number] }];
    saveOffice(s.stations, decor, s.roomSize);
    return { decor };
  }),
  moveDecor: (id, pos) => set((s) => {
    const decor = s.decor.map((d) => (d.id === id ? { ...d, pos } : d));
    saveOffice(s.stations, decor, s.roomSize);
    return { decor };
  }),
  removeDecor: (id) => set((s) => {
    const decor = s.decor.filter((d) => d.id !== id);
    saveOffice(s.stations, decor, s.roomSize);
    return { decor };
  }),
  setRoomSize: (width, depth) => set((s) => {
    const room = { width: clampN(width, ROOM_MIN.width, ROOM_MAX.width), depth: clampN(depth, ROOM_MIN.depth, ROOM_MAX.depth) };
    const fit = fitToRoom(s.stations, s.decor, s.agents, room.width, room.depth);
    saveOffice(fit.stations, fit.decor, room);
    return { roomSize: room, ...fit };
  }),
  resetRoomSize: () => set((s) => {
    const W = s.scene?.room.width ?? 12, D = s.scene?.room.depth ?? 10;
    const fit = fitToRoom(s.stations, s.decor, s.agents, W, D);
    saveOffice(fit.stations, fit.decor, null);
    return { roomSize: null, ...fit };
  }),
  setAgentColor: (id, color) => set((s) => {
    const agent = s.agents[id];
    if (!agent) return s;
    return { agents: { ...s.agents, [id]: { ...agent, color } } };
  }),
}));

function stationBase(scene: Scene | null, name: string): [number, number] {
  const p = scene?.primitives.find((x) => x.name === name);
  if (p) return [p.transform.position[0], p.transform.position[2]];
  const lounge = scene?.primitives.find((x) => x.name === "Lounge");
  return lounge ? [lounge.transform.position[0], lounge.transform.position[2]] : [1.5, 8.5];
}

function stationPos(scene: Scene | null, name: string, id: string): [number, number, number] {
  const [bx, bz] = stationBase(scene, name);
  const [dx, dz] = offsetFor(id);
  return [bx + dx, 0, bz + dz];
}

// Each agent's home is its dedicated desk station (assigned via ensureStations);
// fall back to the manifest home primitive if somehow unassigned.
function homeStation(scene: Scene | null, id: string, home: string, stations: Stations): [number, number, number] {
  const s = stations[id];
  if (s) return [s[0], 0, s[1]];
  return stationPos(scene, home, id);
}

// Agents work at their OWN desk. Movement happens only for the hand-off errand
// (see below) or explicit station states (reviewing/blocked → gate).
function targetFor(scene: Scene | null, home: string, state: string, id: string, stations: Stations): [number, number, number] {
  const station = STATE_STATION[state];
  if (station) return stationPos(scene, station, id);
  return homeStation(scene, id, home, stations);
}

function setPrimitiveActive(scene: Scene, name: string, active: boolean) {
  const p = scene.primitives.find((x) => x.name === name);
  if (p) p.active = active;
}

function toLogLine(e: SamsEvent): LogLine | null {
  if (e.type === "agent.log") {
    return { ts: e.ts, level: e.payload.level ?? "INFO", actor: e.actor, message: e.payload.message };
  }
  const map: Record<string, string> = {
    "agent.spawned": "spawned",
    "agent.task.completed": `completed: ${e.payload.title ?? ""}`,
    "agent.error": `ERROR: ${e.payload.error ?? ""}`,
    "kanban.card.moved": `card ${e.payload.card_id} → ${e.payload.to}`,
    "kanban.card.created": `card created: ${e.payload.title ?? ""}`,
    "vault.file.changed": `wrote ${e.payload.uri ?? ""}`,
    "security.gate.requested": `gate requested: ${e.payload.summary ?? ""}`,
    "security.gate.approved": `gate approved by ${e.payload.approver ?? ""}`,
    "flow.started": `workflow ${e.payload.workflow} started`,
    "flow.completed": `workflow ${e.payload.workflow} completed`,
    "flow.step.started": `step ${e.payload.step} started`,
    "project.started": `▶ started ${e.payload.name}: ${e.payload.command} (pid ${e.payload.pid})`,
    "project.stopped": `■ stopped ${e.payload.name}`,
    "kanban.card.stage": `${e.payload.card_id} · ${e.payload.stage ?? ""} → ${e.payload.status ?? e.payload.stage_status ?? ""}`,
    "project.edited": `✏️ edited ${(e.payload.project ?? "").split("/").pop()}: ${(e.payload.changed ?? []).length} file(s) changed`,
  };
  const msg = map[e.type];
  if (!msg) return null;
  const level = e.type.includes("error") ? "ERROR" : e.type.includes("completed") || e.type.includes("approved") ? "SUCCESS" : "INFO";
  return { ts: e.ts, level, actor: e.actor, message: msg };
}
